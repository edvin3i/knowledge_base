---
tags:
  - polyvision
  - stack
  - adr
  - technology-decisions
created: 2026-02-17
---

# Polyvision -- Стек технологий

## Что это

Документация решений по выбору технологий для платформы [[Polyvision]]. Каждое решение включает альтернативы, обоснование и trade-offs.

## Решения по технологиям

### PyJWT вместо python-jose

| | PyJWT[crypto] | python-jose |
|---|---|---|
| **Статус** | Активная разработка, 5k+ stars | Мертв с 2021, 1.5k stars |
| **Алгоритмы** | RS256, EdDSA, ES256, HS256 | RS256, ES256, HS256 |
| **EdDSA** | Да (через cryptography backend) | Нет |
| **Зависимость** | `cryptography` (OpenSSL bindings) | `ecdsa`, `rsa`, `pyasn1` (чистый Python) |
| **Производительность** | Быстрее (C extensions) | Медленнее (pure Python RSA) |

**Решение**: PyJWT[crypto] -- единственный вариант для RS256 (пользователи) + EdDSA (камеры) в одном пакете. python-jose мертв с 2021, не поддерживает EdDSA.

### Apache APISIX вместо Kong / Traefik / Custom

| Решение | Плюсы | Минусы | Вердикт |
|---------|-------|--------|---------|
| **Custom FastAPI** | Простой, Python-native | Нет hot reload, заново изобретает колесо, O(n) routing | Отклонен |
| **Traefik** | Уже в K3s homelab | Нет custom JWT логики, ограниченные плагины | Отклонен |
| **Kong OSS** | 345k deployments, зрелая экосистема | Только Lua плагины, расхождение OSS/Enterprise с v3.9, O(n) routing | Отклонен |
| **Envoy/Istio** | Service mesh стандарт | Тяжелый для нашего масштаба | Отклонен |
| **Apache APISIX** | 10x perf с плагинами, O(k) routing, Python плагины | etcd зависимость в prod | **Принят** |

**Ключевые факторы**:
- **Python плагины** -- unified JWT validator (RS256 + EdDSA) переиспользует PyJWT стек бекенда
- **Производительность** -- 10x vs Kong с включенными плагинами; radix tree O(k) vs O(n)
- **Apache Foundation** -- полностью open source, нет OSS/Enterprise split
- **Rate limiting** -- использует существующий `redis-cache` для распределенных счетчиков
- **Развертывание**: Standalone (YAML, без deps) для dev -> etcd для prod hot reload

### ClickHouse вместо TimescaleDB / InfluxDB

| Решение | Плюсы | Минусы | Вердикт |
|---------|-------|--------|---------|
| **TimescaleDB** | PostgreSQL extension, SQL совместимость | Медленнее аналитических запросов чем columnar stores | Отклонен |
| **InfluxDB** | Оптимизирован для метрик | Для float метрик, не для event data с bbox/class/confidence | Отклонен |
| **QuestDB** | Быстрый | Менее зрелая экосистема | Отклонен |
| **ClickHouse** | Sub-second аналитика на миллионах строк, materialized views, 10x compression | Дополнительная инфраструктура (+ Keeper) | **Принят** |

**Характеристики данных**:
- ~4.5M записей на 90-минутный матч (324K кадров x ~14 детекций/кадр)
- Immutable после обработки (write once, read many)
- Паттерны доступа: time-range запросы, агрегации, хитмапы
- Партиционирование по `toYYYYMM(created_at)`, tenant isolation через `organization_id`
- TTL 90 дней в ClickHouse, Parquet архив в MinIO на 2 года

### Redpanda вместо RabbitMQ

| Решение | Плюсы | Минусы | Вердикт |
|---------|-------|--------|---------|
| **RabbitMQ** | Зрелый, AMQP протокол | Нет event replay, нет log compaction | Отклонен |
| **Apache Kafka** | Стандарт event streaming | Требует Zookeeper (до KRaft), тяжелый | Не рассматривался |
| **Redpanda** | Kafka-compatible API, без Zookeeper, C++ | Меньше экосистема чем Kafka | **Принят** |

**Топики Redpanda**:
- `polyvision.jobs.commands` -- создание/отмена задач
- `polyvision.jobs.events` -- прогресс, завершение, ошибки
- `polyvision.matches.events` -- загрузка, обработка, готовность
- `polyvision.analytics.events` -- вычисления, запросы
- `polyvision.plugins.events` -- регистрация, health
- `polyvision.devices.events` -- провизионирование, heartbeat

### Dual Redis (cache + celery)

Два инстанса Redis с разными eviction policies:

| Инстанс | Назначение | Eviction Policy | Обоснование |
|---------|-----------|-----------------|-------------|
| `redis-cache` | API кеш, сессии, analytics cache, APISIX rate limiting | `allkeys-lru` | Кеш можно безопасно вытеснять |
| `redis-celery` | Celery broker (task queue + results) | `noeviction` | Задачи нельзя терять -- silent task loss при eviction |

**Почему не один Redis**: При `allkeys-lru` Redis может вытеснить Celery задачи под давлением кеша. При `noeviction` кеш не будет работать при заполнении памяти. Разные workloads требуют разных стратегий.

### Ed25519 для камер, RS256 для пользователей

| Сценарий | Алгоритм | Обоснование |
|----------|----------|-------------|
| **User JWT** | RS256 (RSA 2048-bit) | Индустриальный стандарт, широкая совместимость, APISIX built-in поддержка |
| **Device auth** | Ed25519 | Компактные ключи (32 bytes), быстрая верификация, идеально для IoT/embedded |
| **Device JWT** | EdDSA | Подпись через Ed25519, 30-day expiry, содержит serial + org binding |

**Поток аутентификации камеры**:
1. При сборке -- генерация Ed25519 keypair на устройстве
2. Публичный ключ загружается на платформу через Factory API
3. Challenge-response: устройство запрашивает nonce, подписывает приватным ключом
4. Платформа верифицирует подпись, выдает JWT (EdDSA, 30 дней)
5. Приватный ключ никогда не покидает устройство

### PgBouncer с statement_cache_size=0

**Проблема**: asyncpg использует prepared statements, PgBouncer в transaction mode не поддерживает их по умолчанию.

**Решение**: `statement_cache_size=0` в конфиге PgBouncer отключает серверный кеш prepared statements, обеспечивая совместимость с asyncpg.

```
[pgbouncer]
pool_mode = transaction
server_reset_query = DISCARD ALL
statement_cache_size = 0
```

## Полный список зависимостей

### Backend Services (Python)

| Пакет | Назначение |
|-------|-----------|
| `fastapi` | Web framework для микросервисов |
| `uvicorn[standard]` | ASGI сервер |
| `sqlalchemy[asyncio]` | ORM, async mode |
| `asyncpg` | PostgreSQL async driver |
| `pydantic` v2 | Валидация данных, settings |
| `pyjwt[crypto]` | JWT токены (RS256 + EdDSA) |
| `cryptography` | Криптографические операции (Ed25519, RSA) |
| `celery[redis]` | Task queue |
| `redis` / `hiredis` | Redis клиент с C парсером |
| `clickhouse-driver` | ClickHouse native protocol |
| `boto3` / `aiobotocore` | S3/MinIO клиент |
| `confluent-kafka` | Redpanda/Kafka producer/consumer |
| `httpx` | Async HTTP клиент для inter-service calls |
| `pydantic-settings` | Конфигурация из env переменных |
| `alembic` | Database migrations |
| `prometheus-client` | Метрики |
| `opentelemetry-*` | Distributed tracing |
| `structlog` | Structured logging |

### DeepStream 7.1 Version Lock (ADR-003)

**Решение**: Зафиксировать DS 7.1 на обеих платформах (edge + server).

**Причины:**
- DS 8.0 **не поддерживает Jetson Orin NX** (только Jetson Thor)
- Split (server 8.0 + edge 7.1) создает два окружения и двойное CI
- MV3DT из DS 8.0 не применим к нашему rig (baseline ~20-30 см, ΔZ ≈ 2.8м на 50м)
- Ubuntu 22.04 → 24.04 — нетривиальная миграция стека
- DS 7.1 активно поддерживается, EOL не анонсирован

**DS 8.0 фичи не доступные нам**: MaskTracker (SAM2), MV3DT, Pose estimation, TRT 10.9
**Пересмотр**: Q3 2026 — после выхода JetPack 7.2

Подробнее: [[PV-DeepStream]]

### Калибровка камер: 2D + Field Homography (ADR-024)

Два уровня калибровки:
1. **Stitching LUT** (2D→2D) — склейка L/R в панораму (CUDA kernel, 50 FPS)
2. **Field Homography** (pixels→meters) — проекция на плоскость поля (105m × 68m)

**Не используем**: Full 3D calibration (intrinsics + extrinsics) — baseline слишком мал для stereo.

### Edge Pipeline (Jetson)

| Пакет / SDK | Назначение |
|-------------|-----------|
| `deepstream-7.1` | Video processing pipeline (version locked) |
| `tensorrt` 10.3 | Model inference engine |
| `pybind11` | C++/Python bindings для `sports-analytics-core` |
| `numpy` | Массивы данных |
| `gi` (PyGObject) | GStreamer bindings |

### Инфраструктура

| Компонент           | Назначение                     |
| ------------------- | ------------------------------ |
| `apache-apisix`     | API Gateway                    |
| `etcd`              | Config store для APISIX (prod) |
| `postgresql` 17     | Основная СУБД                  |
| `pgbouncer`         | Connection pooling             |
| `clickhouse-server` | Аналитическая СУБД             |
| `clickhouse-keeper` | Consensus для ClickHouse       |
| `redis` 8           | Кеш + Celery broker            |
| `redpanda`          | Event streaming                |
| `minio`             | Object storage                 |
| `prometheus`        | Сбор метрик                    |
| `grafana`           | Дашборды                       |
| `loki`              | Агрегация логов                |
| `jaeger` / `tempo`  | Трейсинг                       |

### Разработка и CI

| Инструмент | Назначение |
|-----------|-----------|
| `uv` | Package manager (замена pip/poetry) |
| `ruff` | Linter + formatter |
| `mypy` | Type checking |
| `pytest` | Тестирование |
| `bandit` | Security scanning |

## Связано с

- [[Polyvision]] -- обзор проекта
- [[SystemDesign]] -- учебные материалы
- [[PV-Messaging]] -- Redpanda + Redis архитектура
- [[PV-Orchestration]] -- Celery + state machine

## Ресурсы

- Apache APISIX: https://apisix.apache.org/
- ClickHouse: https://clickhouse.com/docs
- Redpanda: https://docs.redpanda.com/
- PyJWT: https://pyjwt.readthedocs.io/
- Ed25519: https://ed25519.cr.yp.to/
- Репозиторий: `~/Expirements/polyvision/docs/decisions.md`

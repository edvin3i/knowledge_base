---
tags:
  - project
  - moc
  - polyvision
  - sports-analytics
created: 2026-02-17
---

# Polyvision

## Что это

Polyvision -- платформа спортивной аналитики для обработки футбольных матчей с двух 4K камер. Три слоя: Frontend (веб/мобильные вьюеры), Edge (Jetson Orin NX -- "умная камера"), Backend (офлайн обработка, VOD, аналитика). Принцип: **"Обработай один раз, обслуживай тысячам"** (Process Once, Serve Many) -- дорогая GPU-обработка выполняется один раз, артефакты кешируются и раздаются тысячам зрителей.

## Архитектура

8+ микросервисов на FastAPI за Apache APISIX gateway:

| Сервис | Порт | Назначение |
|--------|------|------------|
| **Gateway** (Apache APISIX) | :8000 | Маршрутизация, JWT валидация (RS256 + EdDSA), rate limiting, CORS, security headers |
| **Auth Service** | :8001 | Email/password аутентификация, JWT RS256, сессии в Redis |
| **Ingestion Service** | :8002 | Валидация пакетов с камер, S3 multipart upload |
| **Catalog Service** | :8003 | Матчи, команды, активы, ACL проверки |
| **Processing Orchestrator** | :8004 | State machine обработки, retry, идемпотентность, HA через Redpanda leader election |
| **Analytics Query API** | :8005 | Запросы к ClickHouse: треки, хитмапы, статистика |
| **Delivery Service** | :8006 | HLS/DASH манифесты, подписанные URL, CDN интеграция |
| **Device Service** | :8007 | Реестр устройств, Ed25519 аутентификация камер, провизионирование |
| **Entitlements/Payments** | TBD | Stripe webhooks, подписки по организациям |

### Пайплайн обработки

8 стадий от исходного видео до готового контента:

1. **ingest** -- валидация файлов, проверка совпадения количества кадров left/right
2. **stitch** -- генерация панорамы 5700x1669 (DeepStream) -> MinIO
3. **detect** -- детекция на тайлах (6x1024 или 18x640) -> ClickHouse
4. **track** -- построение траекторий, интерполяция пропусков -> ClickHouse
5. **vcam** -- генерация виртуальной камеры -> MinIO
6. **analyze** -- хитмапы, статистика, события -> MinIO + ClickHouse materialized views
7. **encode** -- транскодирование в HLS варианты -> MinIO
8. **index** -- генерация summary, обновление поисковых индексов

### GPU Workers

- **Stitch Worker** -- `stitch_core` / nvdsstitch (LUT-based CUDA kernel)
- **Detect Worker** -- tilebatcher + TensorRT/DeepStream (модели через Model Registry)
- **VirtualCam Worker** -- `vcam_core` / nvdsvirtualcam (3 режима: Director/Zones/Centered)

### CPU/IO Workers

- **Packager Worker** -- HLS/DASH + рендиции, превью
- **Indexer/ETL Worker** -- summary + поисковые индексы

## Стек технологий

Подробности выбора: [[Polyvision-Stack]]

### Основные технологии

- **Python 3.12+**, uv (package manager), FastAPI, SQLAlchemy 2.0 async, Pydantic v2
- **C++/CUDA** (`sports-analytics-core`) через pybind11 -- shared library для Edge и Backend
- **DeepStream 7.1** -- видео-пайплайны (GStreamer + TensorRT)

### Хранение данных

- **PostgreSQL** -- метаданные, тенанты, задания, события
- **ClickHouse** -- детекции (~4.5M записей/матч), траектории, materialized views (90-day TTL)
- **MinIO** (S3-совместимое) -> Ceph (план) -- видео, артефакты, HLS сегменты
- **Redis**: `redis-cache` (allkeys-lru) + `redis-celery` (noeviction)

### Messaging и оркестрация

- **Redpanda** -- Kafka-compatible event streaming, без Zookeeper
- **Celery** -- task queue через `redis-celery`
- **Apache APISIX** -- API Gateway (Standalone в dev, etcd в prod)

### Аутентификация

- **PyJWT[crypto]** (НЕ python-jose -- мертв с 2021)
- **RS256** -- JWT для пользователей
- **Ed25519** -- аутентификация камер (Device Service)

### Наблюдаемость

- **Prometheus/Grafana** -- метрики
- **Loki** -- логи
- **OpenTelemetry** -- трейсинг

## Edge устройство

**Jetson Orin NX 16GB** -- "умная камера" для прямых трансляций:

- **Камеры**: 2x Sony IMX678 STARVIS 2 (MIPI CSI-2)
- **Разрешение**: 3856x2180 @ 60 FPS (нативное сенсора, НЕ 3840x2160 -- иначе +20ms ISP latency)
- **Синхронизация**: XVS/XHS Master-Slave на J4 коннекторах (аппаратный frame sync)
- **Панорама**: 5700x1669 при 50 FPS (LUT-based CUDA kernel)
- **Детекция**: Object detection на 18x640 тайлах (sub-batched mode)
- **Виртуальная камера**: 3 режима с physics-based smoothing

```
Cameras (2x IMX678) -> nvstreammux -> nvdsstitch (panorama 5700x1669)
                                          |
                                        [tee]
                        +------------------+------------------+
                        |                                     |
               Analysis branch                        Display branch
          (nvtilebatcher -> nvinfer               (nvdsvirtualcam -> encode
           -> AnalysisProbe)                       -> RTMP stream)
```

Детекция на edge **отбрасывается** после стрима (только для live auto-tracking). Полная обработка -- на бекенде.

## Multi-Tenancy

Организации (`organizations`) с таблицей принадлежности (`organization_memberships`). Роли: owner / admin / analyst / viewer. Подписки и entitlements -- per-organization. ClickHouse изолирует данные через `organization_id` в ORDER BY.

## Staging

Homelab K3s кластер:
- 3x [[polynode-1]] / [[polynode-2]] / [[polynode-3]] (Dell OptiPlex 3050)
- polydev-desktop с RTX A6000 (GPU worker)
- [[K3s]] оркестрация
- [[MinIO]] для object storage

## Ключевые ADR

| ADR | Решение | Суть |
|-----|---------|------|
| ADR-009 | Redpanda + Redis | Event streaming через Redpanda, Celery broker через Redis (noeviction) |
| ADR-021 | ClickHouse | Детекции ~4.5M записей/матч, 90-day TTL, materialized views для хитмап |
| ADR-022 | Ed25519 device auth | Асимметричная аутентификация камер, приватный ключ никогда не покидает устройство |
| ADR-023 | Apache APISIX | API Gateway с Python плагинами, 10x производительность vs Kong, Apache Foundation |

Полный список: `docs/decisions.md` в репозитории.

## Связано с

- [[Homelab]] -- инфраструктура staging окружения
- [[K3s]] -- оркестрация контейнеров
- [[MinIO]] -- object storage
- [[CVAT]] -- разметка данных для обучения моделей
- [[ClearML]] -- MLOps платформа
- [[Polyvision-Stack]] -- решения по выбору технологий
- [[SystemDesign]] -- учебные материалы по проектированию систем
- [[PV-Orchestration]] -- паттерны оркестрации в Polyvision
- [[PV-Messaging]] -- event streaming и message broker решения

## Ресурсы

- Репозиторий: `~/Expirements/polyvision`
- Конфигурация Claude Code: `CLAUDE.md`
- Архитектурные решения: `docs/decisions.md`
- Архитектура бекенда: `docs/backend-architecture.md`
- Edge pipeline: `docs/edge-pipeline.md`
- Микросервисы и схемы: `docs/microservices-schemas.md`

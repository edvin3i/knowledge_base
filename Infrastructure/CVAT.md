---
tags:
  - kubernetes
  - ml
  - annotation
  - infrastructure
created: 2026-01-19
updated: 2026-01-29
---

# CVAT

Computer Vision Annotation Tool — платформа для аннотации данных в [[K3s]] кластере.

## Теория: Что такое CVAT

### Назначение

**CVAT (Computer Vision Annotation Tool)** — open-source инструмент для разметки данных в задачах компьютерного зрения:
- Классификация изображений
- Object detection (bounding boxes)
- Semantic/Instance segmentation
- Pose estimation
- Tracking объектов в видео

### Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                       CVAT Architecture                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Browser ──► Ingress ──► Frontend (nginx)                      │
│                  │                                               │
│                  └──► Backend (Django)                          │
│                           │                                      │
│         ┌─────────────────┼─────────────────┐                   │
│         ▼                 ▼                 ▼                   │
│   ┌──────────┐     ┌──────────┐     ┌──────────┐               │
│   │PostgreSQL│     │  Redis   │     │ KVRocks  │               │
│   │   (DB)   │     │ (cache)  │     │(on-disk) │               │
│   └──────────┘     └──────────┘     └──────────┘               │
│                                                                  │
│   Workers (Celery):                                             │
│   ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐                  │
│   │ import │ │ export │ │ chunks │ │annotate│ ...              │
│   └────────┘ └────────┘ └────────┘ └────────┘                  │
│                                                                  │
│   Analytics:                                                     │
│   ┌────────┐ ┌────────────┐ ┌────────┐                         │
│   │ Vector │►│ ClickHouse │►│Grafana │                         │
│   │ (logs) │ │ (storage)  │ │ (UI)   │                         │
│   └────────┘ └────────────┘ └────────┘                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Компоненты:**

| Компонент | Назначение |
|-----------|------------|
| **Frontend** | React UI (nginx) |
| **Backend** | Django REST API |
| **PostgreSQL** | Основная БД (пользователи, проекты, задачи) |
| **Redis** | Кэш и очередь задач |
| **KVRocks** | On-disk key-value (большие данные) |
| **Workers** | Celery workers для async задач |
| **OPA** | Open Policy Agent (авторизация) |
| **Vector** | Сбор логов |
| **ClickHouse** | Хранение аналитики |
| **Grafana** | Дашборды аналитики |

---

## Статус

| Параметр | Значение |
|----------|----------|
| **Версия** | 2.39.0 |
| **Namespace** | `cvat` |
| **Chart version** | 0.17.1 |
| **Nuclio** | v1.15.13 |
| **Registry** | docker.io/edvin3i |
| **CVAT IP** | 192.168.20.235 ([[MetalLB]]) |
| **Nuclio IP** | 192.168.20.236 ([[MetalLB]]) |

### Текущее состояние

- CVAT UI доступен на http://192.168.20.235
- Nuclio controller и dashboard работают
- GPU функция `yolo11x-cvat-detector-gpu` работает на [[polydev-desktop]]
- Analytics (Grafana + ClickHouse + Vector) настроены

## Доступ

### Через port-forward

```bash
# Frontend UI
kubectl port-forward svc/cvat-frontend-service 8080:80 -n cvat
# Открыть http://localhost:8080

# Backend API
kubectl port-forward svc/cvat-backend-service 8081:8080 -n cvat
# API доступен на http://localhost:8081/api

# Grafana Analytics
kubectl port-forward svc/cvat-grafana 3000:80 -n cvat
# Открыть http://localhost:3000
```

### Через Ingress (рекомендуется)

Требуется [[MetalLB]] для назначения IP адреса Traefik LoadBalancer.

Доступно по IP напрямую (без /etc/hosts):
- **CVAT UI:** http://192.168.20.235
- **Analytics:** http://192.168.20.235/analytics
- **Nuclio Dashboard:** http://192.168.20.236

**Проверить IP Traefik:**

```bash
kubectl get svc -n kube-system traefik -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

**Примечание:** Ingress настроен без hostname (`HOSTS: *`), принимает запросы на любой host/IP.

---

## Установка

### Подготовка Helm chart

```bash
# Клонировать CVAT
git clone https://github.com/cvat-ai/cvat.git
cd cvat

# Обновить зависимости
cd helm-chart
helm dependency update
```

### Исправления для K3s

**Проблема 1:** Security context требует numeric UID.

CVAT образы используют именованных пользователей (`django`, `kvrocks`), что вызывает ошибку `runAsNonRoot`.

**Решение:** Добавить `runAsUser` в templates:

```bash
# Для backend (UID 1000 - django user)
find templates -name "*.yml" -exec grep -l "runAsNonRoot: true" {} \; | \
while read file; do
  sed -i 's/runAsNonRoot: true/runAsNonRoot: true\n            runAsUser: 1000/g' "$file"
done
```

Исключения:
- **Frontend** (`cvat/ui`) — работает как root, убрать securityContext
- **KVRocks** — использует UID 999

**Проблема 2:** Отсутствуют конфиги analytics.

```bash
# Скопировать vector и grafana конфиги
mkdir -p helm-chart/analytics/vector
mkdir -p helm-chart/analytics/grafana/dashboards

cp components/analytics/vector/vector.toml helm-chart/analytics/vector/
cp components/analytics/grafana/dashboards/*.json helm-chart/analytics/grafana/dashboards/
```

**Проблема 3:** Frontend слушает порт 80, не 8000.

В `templates/cvat_frontend/deployment.yml` изменить все `port: 8000` на `port: 80`.

### values.yaml для кластера

```yaml
cvat:
  backend:
    image: cvat/server
    tag: v2.39.0
    imagePullPolicy: IfNotPresent
    defaultStorage:
      enabled: true
      size: 50Gi
    server:
      replicas: 1
    worker:
      export:
        replicas: 1
      import:
        replicas: 1
      annotation:
        replicas: 1
      webhooks:
        replicas: 1
      qualityreports:
        replicas: 1
      chunks:
        replicas: 1
      consensus:
        replicas: 1
      utils:
        replicas: 1

  frontend:
    replicas: 1
    image: cvat/ui
    tag: v2.39.0
    service:
      type: ClusterIP
      ports:
        - port: 80
          targetPort: 80
          protocol: TCP
          name: http

  kvrocks:
    enabled: true
    defaultStorage:
      enabled: true
      size: 30Gi

postgresql:
  enabled: true
  primary:
    persistence:
      enabled: true
      size: 10Gi

redis:
  enabled: true
  architecture: standalone

nuclio:
  enabled: false

analytics:
  enabled: true

clickhouse:
  enabled: true
  shards: 1
  replicaCount: 1

grafana:
  persistence:
    enabled: true
    size: 5Gi

ingress:
  enabled: true
  hostname: cvat.local
  className: traefik
  tls: false

traefik:
  enabled: false
```

### Установка

```bash
helm install cvat ./helm-chart \
  --namespace cvat \
  --create-namespace \
  -f cvat-values.yaml
```

### Проверка

```bash
# Все поды должны быть Running
kubectl get pods -n cvat

# Проверить API
kubectl port-forward svc/cvat-backend-service 8081:8080 -n cvat &
curl http://localhost:8081/api/server/about
```

---

## Создание суперпользователя

После установки CVAT нужно создать администратора для доступа к системе.

### Команда

```bash
# Получить имя пода backend server
POD=$(kubectl get pods -n cvat -l tier=backend -o jsonpath='{.items[0].metadata.name}')

# Создать суперпользователя
kubectl exec -it $POD -n cvat -- python manage.py createsuperuser
```

### Процесс

```
Username: admin
Email address: admin@example.com
Password: ********
Password (again): ********
Superuser created successfully.
```

**Разбор команды:**

| Элемент | Объяснение |
|---------|------------|
| `kubectl exec -it` | Выполнить команду в контейнере интерактивно |
| `$POD` | Имя пода (cvat-backend-server-xxx) |
| `-n cvat` | Namespace |
| `--` | Разделитель kubectl и команды в контейнере |
| `python manage.py` | Django management команда |
| `createsuperuser` | Создать пользователя с правами админа |

### Альтернатива: неинтерактивное создание

```bash
# Через переменные окружения
kubectl exec -it $POD -n cvat -- python manage.py shell -c "
from django.contrib.auth.models import User
User.objects.create_superuser('admin', 'admin@example.com', 'your_password')
"
```

### Проверка

После создания суперпользователя:

1. Открыть CVAT UI:
   ```bash
   kubectl port-forward svc/cvat-frontend-service 8080:80 -n cvat
   ```
2. Перейти на http://localhost:8080
3. Войти с созданными credentials

### Управление пользователями

```bash
# Список пользователей
kubectl exec -it $POD -n cvat -- python manage.py shell -c "
from django.contrib.auth.models import User
for u in User.objects.all():
    print(f'{u.username} - {u.email} - superuser: {u.is_superuser}')
"

# Изменить пароль пользователя
kubectl exec -it $POD -n cvat -- python manage.py changepassword admin

# Сделать существующего пользователя суперпользователем
kubectl exec -it $POD -n cvat -- python manage.py shell -c "
from django.contrib.auth.models import User
u = User.objects.get(username='username')
u.is_superuser = True
u.is_staff = True
u.save()
"
```

---

## Обновление

```bash
helm upgrade cvat ./helm-chart \
  --namespace cvat \
  -f cvat-values.yaml
```

---

## Storage

CVAT использует [[Longhorn]] для хранения:

| PVC | Назначение | Размер |
|-----|------------|--------|
| `cvat-backend-data` | Данные проектов, задач | 50Gi |
| `cvat-kvrocks-data` | KVRocks storage | 50Gi (расширен с 35Gi 2026-02-10, с 30Gi 2026-02-06, с 20Gi 2026-01-29), 1 реплика на polydev-desktop |
| `data-cvat-postgresql-0` | PostgreSQL | 10Gi |
| `data-cvat-clickhouse-shard0-0` | ClickHouse | 10Gi |

```bash
kubectl get pvc -n cvat
```

---

## Полезные команды

```bash
# Логи backend
kubectl logs -n cvat -l tier=backend -l app=cvat-app-server --tail=100

# Логи worker
kubectl logs -n cvat -l tier=worker-import --tail=100

# Shell в backend
kubectl exec -it deployment/cvat-backend-server -n cvat -- /bin/bash

# Проверить очереди Redis
kubectl exec -it cvat-redis-master-0 -n cvat -- redis-cli info

# Рестарт всех worker'ов
kubectl rollout restart deployment -n cvat -l app=cvat-app
```

---

## Troubleshooting

### CreateContainerConfigError

**Симптом:** Поды не запускаются, ошибка `runAsNonRoot`.

**Причина:** Security context требует numeric UID.

**Решение:** Добавить `runAsUser: 1000` (или 999 для kvrocks) в templates.

### Vector CrashLoopBackOff

**Симптом:** Vector pod падает с ошибкой "No sources defined".

**Причина:** Отсутствует конфиг `vector.toml`.

**Решение:** Скопировать конфиг из `components/analytics/vector/`.

### Frontend Liveness Probe Failed

**Симптом:** Frontend постоянно перезапускается.

**Причина:** Probe проверяет порт 8000, nginx слушает 80.

**Решение:** Изменить порты в deployment template на 80.

### Ingress не работает (EXTERNAL-IP pending)

**Симптом:** `kubectl get svc traefik -n kube-system` показывает `EXTERNAL-IP: <pending>`.

**Причина:** Нет LoadBalancer контроллера.

**Решение:** Установить [[MetalLB]].

**Проверить:**
1. Traefik в K3s работает:
```bash
kubectl get pods -n kube-system -l app.kubernetes.io/name=traefik
```

2. Ingress создан:
```bash
kubectl describe ingress cvat -n cvat
```

3. DNS/hosts настроен:
```bash
ping cvat.local
```

### ClickHouse база не создана (Helm chart bug)

**Симптом:** Grafana показывает ошибку `Database cvat does not exist`.

**Причина:** Helm chart CVAT не включает Job для инициализации ClickHouse — это недоработка чарта. В docker-compose версии есть `init.py`, но в Helm он не запускается.

**Решение:** Создать базу и таблицу вручную:

```bash
kubectl exec -it cvat-clickhouse-shard0-0 -n cvat -- clickhouse-client --multiquery -q "
CREATE DATABASE IF NOT EXISTS cvat;

CREATE TABLE IF NOT EXISTS cvat.events
(
    scope String NOT NULL,
    obj_name String NULL,
    obj_id UInt64 NULL,
    obj_val String NULL,
    source String NOT NULL,
    timestamp DateTime64(3, 'Etc/UTC') NOT NULL,
    count UInt16 NULL,
    duration UInt32 DEFAULT toUInt32(0),
    project_id UInt64 NULL,
    task_id UInt64 NULL,
    job_id UInt64 NULL,
    user_id UInt64 NULL,
    user_name String NULL,
    user_email String NULL,
    org_id UInt64 NULL,
    org_slug String NULL,
    payload String NULL,
    access_token_id Nullable(UInt64) DEFAULT NULL
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp)
SETTINGS index_granularity = 8192;
"
```

После этого перезапустить Vector:

```bash
kubectl delete pod cvat-vector-0 -n cvat
```

### Grafana не загружается через /analytics

**Симптом:** Ошибка "Grafana has failed to load its application files" при доступе через subpath.

**Причина:** Grafana не настроена для работы из subpath.

**Решение:** Добавить в `cvat-values.yaml`:

```yaml
grafana:
  grafana.ini:
    server:
      root_url: "%(protocol)s://%(domain)s/analytics"
      serve_from_sub_path: true
```

И обновить:

```bash
helm upgrade cvat ./helm-chart -n cvat -f cvat-values.yaml
```

### Cloud Storage: "Resource not found" при подключении MinIO

**Симптом:** При создании Cloud Storage в CVAT UI ошибка:
```
Could not create the cloud storage
resource: The resource <bucket> not found. It may have been deleted.
```

**Причина:** CVAT использует **Smokescreen** — HTTP proxy для защиты от [SSRF атак](https://owasp.org/API-Security/editions/2023/en/0xa7-server-side-request-forgery/). По умолчанию Smokescreen блокирует все приватные IP диапазоны.

#### Теория: Что такое SSRF и Smokescreen

**SSRF (Server-Side Request Forgery)** — атака, при которой злоумышленник заставляет сервер делать запросы к внутренним ресурсам:

```
┌─────────────────────────────────────────────────────────────────┐
│                         SSRF Attack                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Attacker                                                       │
│      │                                                           │
│      │ 1. "Add cloud storage: http://169.254.169.254"           │
│      ▼                                                           │
│   ┌─────────┐                                                    │
│   │  CVAT   │  2. CVAT делает запрос к указанному URL           │
│   │ Backend │─────────────────────┐                              │
│   └─────────┘                     │                              │
│                                   ▼                              │
│                            ┌─────────────┐                       │
│                            │ Cloud Meta  │  ← AWS/GCP metadata   │
│                            │ 169.254.x.x │     API с credentials │
│                            └─────────────┘                       │
│                                                                  │
│   Или: http://10.43.x.x ─► Internal K8s services                │
│   Или: http://localhost ─► Localhost services                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Smokescreen** ([Stripe](https://github.com/stripe/smokescreen)) — HTTP CONNECT proxy, который:
- Резолвит DNS перед подключением
- Блокирует приватные IP диапазоны (10.x, 172.16.x, 192.168.x, localhost, link-local)
- Логирует все исходящие соединения
- Предотвращает SSRF атаки

```
┌─────────────────────────────────────────────────────────────────┐
│                    Smokescreen Protection                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Request: http://minio.minio.svc.cluster.local                 │
│      │                                                           │
│      │ 1. DNS resolve                                            │
│      ▼                                                           │
│   ┌───────────────┐                                              │
│   │  Smokescreen  │  2. Resolved IP: 10.43.39.217               │
│   │               │  3. Check: Is 10.43.x.x private? YES        │
│   │               │  4. Action: DENY ❌                          │
│   └───────────────┘                                              │
│                                                                  │
│   Log: "destination address was denied by rule                  │
│         'Deny: Private Range'"                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Диагностика

```bash
# Проверить логи backend при попытке создания cloud storage
kubectl logs -n cvat deploy/cvat-backend-server --tail=50 | grep -i smokescreen

# Ожидаемый вывод при блокировке:
# "decision_reason": "The destination address (10.43.39.217) was denied
#  by rule 'Deny: Private Range'"
```

#### Решение: Разрешить внутренний CIDR кластера

Для подключения к MinIO внутри кластера нужно добавить Kubernetes Service CIDR в allow-list.

**Найти Service CIDR:**
```bash
kubectl cluster-info dump | grep -m1 service-cluster-ip-range
# Обычно: 10.43.0.0/16 для K3s
```

**Обновить SMOKESCREEN_OPTS:**
```bash
# Backend server
kubectl set env deploy/cvat-backend-server -n cvat \
  SMOKESCREEN_OPTS="--allow-range=10.43.0.0/16"

# Workers (для import/export с cloud storage)
kubectl set env deploy/cvat-backend-worker-import -n cvat \
  SMOKESCREEN_OPTS="--allow-range=10.43.0.0/16"
kubectl set env deploy/cvat-backend-worker-export -n cvat \
  SMOKESCREEN_OPTS="--allow-range=10.43.0.0/16"

# Дождаться перезапуска
kubectl rollout status deploy/cvat-backend-server -n cvat
```

**Через Helm (постоянное решение):**
```yaml
# cvat-values.yaml
smokescreen:
  opts: "--allow-range=10.43.0.0/16"
```

#### Безопасность: Оценка рисков

| Аспект | Оценка | Комментарий |
|--------|--------|-------------|
| **Риск SSRF** | Низкий | Разрешён только Service CIDR (10.43.x.x), не pod CIDR |
| **Доступные сервисы** | MinIO, внутренние ClusterIP | Не metadata API (169.254.x.x) |
| **Mitigation** | Сетевые политики | NetworkPolicy может ограничить egress |
| **Альтернатива** | `--allow-address` | Точечное разрешение одного IP |

**Более строгий вариант — разрешить только MinIO:**
```bash
# Узнать ClusterIP MinIO
MINIO_IP=$(kubectl get svc minio -n minio -o jsonpath='{.spec.clusterIP}')

kubectl set env deploy/cvat-backend-server -n cvat \
  SMOKESCREEN_OPTS="--allow-address=$MINIO_IP"
```

**Рекомендация для production:**
1. Использовать `--allow-address` вместо `--allow-range` где возможно
2. Добавить NetworkPolicy для ограничения egress CVAT
3. Мониторить логи Smokescreen на подозрительные запросы

#### Настройка Cloud Storage после исправления

После применения fix, в CVAT UI:

| Поле | Значение |
|------|----------|
| Display name | `MinIO Datasets` |
| Provider | AWS S3 |
| Bucket name | `datasets` |
| Access key ID | `fsadm` |
| Secret access key | `minimiAdmin` |
| **Endpoint URL** | `http://minio.minio.svc.cluster.local` |
| Region | `us-east-1` |

**Важно:** Использовать внутренний DNS (`minio.minio.svc.cluster.local`), а не внешний IP.

#### Ссылки

- [Stripe Smokescreen](https://github.com/stripe/smokescreen)
- [OWASP SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [CVAT Issue #6457](https://github.com/cvat-ai/cvat/issues/6457) — Smokescreen errors
- [Material Security: Locking Down Internet Traffic in K8s](https://material.security/blog/locking-down-internet-traffic-in-kubernetes)

---

## Cloud Storage и MinIO интеграция

CVAT поддерживает Cloud Storage для хранения данных, экспорта аннотаций и бэкапов проектов.

### Теория: Source и Target Storage

CVAT различает два типа хранилищ:

```
┌─────────────────────────────────────────────────────────────────┐
│                  CVAT Storage Architecture                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────┐         ┌─────────────────┐              │
│   │ Source Storage  │         │ Target Storage  │              │
│   │  (откуда брать) │         │ (куда сохранять)│              │
│   └────────┬────────┘         └────────┬────────┘              │
│            │                           │                        │
│            ▼                           ▼                        │
│   ┌─────────────────┐         ┌─────────────────┐              │
│   │ MinIO Datasets  │         │ MinIO CVAT      │              │
│   │ s3://datasets/  │         │ s3://cvat/      │              │
│   │                 │         │                 │              │
│   │ - Изображения   │         │ - Экспорты      │              │
│   │ - Видео         │         │ - Бэкапы        │              │
│   │ - Датасеты      │         │ - Аннотации     │              │
│   └─────────────────┘         └─────────────────┘              │
│                                                                  │
│   Workflow:                                                      │
│   1. Task создаётся из Source Storage (images)                  │
│   2. Аннотирование в CVAT UI                                    │
│   3. Export/Backup в Target Storage                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

| Storage Type | Назначение | Пример |
|--------------|------------|--------|
| **Source** | Исходные данные для разметки | `s3://datasets/polyvision/images/` |
| **Target** | Результаты (экспорты, бэкапы) | `s3://cvat/exports/`, `s3://cvat/backups/` |

### Настроенные Cloud Storages

| Display Name | Bucket | Endpoint | Назначение |
|--------------|--------|----------|------------|
| `MinIO Datasets` | `datasets` | `http://minio.minio.svc.cluster.local` | Source — датасеты для разметки |
| `MinIO CVAT Internal` | `cvat` | `http://minio.minio.svc.cluster.local` | Target — экспорты и бэкапы |

### Использование Source Storage

При создании Task можно загружать данные напрямую из Cloud Storage:

1. **Tasks** → **Create Task**
2. **Select files** → **Cloud Storage**
3. Выбрать `MinIO Datasets`
4. Указать путь: `polyvision-cls-5-v1.1/Polyvision_dataset_five_classes_v1.1/images/Train/`
5. Выбрать файлы или использовать pattern `*`

**Manifest (опционально):** Для ускорения загрузки больших датасетов создайте `manifest.jsonl`:

```bash
# На локальной машине
cd /path/to/dataset
python3 -c "
import json
from pathlib import Path

for img in sorted(Path('images/Train').glob('*.jpg')):
    print(json.dumps({'name': str(img)}))
" > manifest.jsonl

# Загрузить в MinIO
mcli cp manifest.jsonl homelab/datasets/polyvision-cls-5-v1.1/
```

### Использование Target Storage

#### Экспорт аннотаций в Cloud Storage

1. **Task/Project** → **Actions** → **Export dataset**
2. Выбрать формат: `YOLO 1.1`, `COCO 1.0`, `CVAT for images 1.1`, etc.
3. **☐ Use default settings** — отключить
4. **Target storage**: `Cloud storage` → `MinIO CVAT Internal`
5. Указать путь (prefix): `exports/polyvision/`
6. **Export**

Результат:
```
s3://cvat/exports/polyvision/annotations_yolo_2026-01-22.zip
```

#### Backup проекта в Cloud Storage

1. **Project** → **Actions** → **Backup**
2. **Custom name**: `polyvision_v1` (опционально)
3. **☑️ Use lightweight backup** — рекомендуется для cloud-sourced данных
4. **☐ Use default settings** — отключить
5. **Target storage**: `Cloud storage` → `MinIO CVAT Internal`
6. **Backup**

**Lightweight backup:**
- Сохраняет только метаданные + аннотации
- НЕ копирует медиафайлы (они уже в Source Storage)
- Значительно быстрее и меньше по размеру

Результат:
```
s3://cvat/backups/polyvision_v1_backup_2026_01_22_12_30.zip
```

### Создание проекта и импорт аннотаций через REST API

Для автоматизации создания проектов, задач и импорта аннотаций используется CVAT REST API.

#### 1. Получение API-токена

```bash
# Через Django shell в backend pod
kubectl exec -n cvat deploy/cvat-backend-server -- python3 -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cvat.settings.production')
django.setup()
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User

user = User.objects.get(username='Ivan89')
token, created = Token.objects.get_or_create(user=user)
print(token.key)
"
```

#### 2. Создание проекта с лейблами

```bash
CVAT_TOKEN="your-token-here"

curl -s -X POST "http://192.168.20.235/api/projects" \
  -H "Authorization: Token $CVAT_TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Organization: Ploycube" \
  -d '{
    "name": "Project Name",
    "labels": [
      {"name": "ball", "color": "#ff6600", "type": "any"},
      {"name": "player", "color": "#00ff00", "type": "any"},
      {"name": "side_referee", "color": "#0066ff", "type": "any"},
      {"name": "main_referee", "color": "#ff0066", "type": "any"}
    ],
    "target_storage": {"location": "cloud_storage", "cloud_storage_id": 3}
  }'
# cloud_storage_id: 3 = MinIO CVAT Internal (org: Ploycube)
# cloud_storage_id: 4 = MinIO Datasets (org: Ploycube)
```

#### 3. Создание задачи из Cloud Storage

**Два этапа:** сначала создать Task (метаданные), затем POST `/data` (привязка файлов).

**Параметры создания задачи:**

| Параметр | Описание | Пример |
|----------|----------|--------|
| `name` | Имя задачи | `"Vincennes-Athletic-small_2026-02-10"` |
| `project_id` | ID проекта (лейблы наследуются) | `4` |
| `segment_size` | Кол-во изображений в одном Job | `1000` |
| `source_storage` | Откуда читать изображения | `cloud_storage_id: 4` |
| `target_storage` | Куда сохранять экспорт | `cloud_storage_id: 3` |

**Параметры data payload:**

| Параметр | Описание | Значения |
|----------|----------|----------|
| `cloud_storage_id` | **Обязательно!** ID Cloud Storage в payload | `4` |
| `server_files` | Массив путей файлов внутри bucket | `["prefix/images/img1.jpg", ...]` |
| `image_quality` | Качество сжатия JPEG chunks (1-100) | `70` (default), `100` (макс. качество, не lossless) |
| `use_zip_chunks` | Упаковать chunks в zip | `true` |
| `use_cache` | Кэшировать chunks | `true` |
| `sorting_method` | Сортировка файлов | `"natural"` |

> **ВАЖНО:** `cloud_storage_id` нужно указывать **и в задаче** (`source_storage`), **и в data payload**. Без `cloud_storage_id` в payload CVAT ищет файлы локально в `/home/django/share/` — даже если `source_storage` задачи указывает на cloud.

> **image_quality и KVRocks:** При `image_quality=100` image chunks не сжимаются и кэшируются в KVRocks as-is. Для задач >1000 изображений это может заполнить KVRocks PVC (см. [[#KVRocks PVC заполнен (No space left on device)]]). Рекомендация: `70` для обычной разметки, `100` только если критично качество.

```bash
# Шаг 1: Создать задачу
curl -s -X POST "http://192.168.20.235/api/tasks" \
  -H "Authorization: Token $CVAT_TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Organization: Ploycube" \
  -d '{
    "name": "Task Name",
    "project_id": 4,
    "segment_size": 1000,
    "source_storage": {
      "location": "cloud_storage",
      "cloud_storage_id": 4
    },
    "target_storage": {
      "location": "cloud_storage",
      "cloud_storage_id": 3
    }
  }'
# Ответ: {"id": 19, "name": "Task Name", ...}
TASK_ID=19

# Шаг 2: Привязать файлы из MinIO
# server_files — массив путей внутри bucket (без имени bucket)
# ВАЖНО: cloud_storage_id обязателен в payload!
curl -s -X POST "http://192.168.20.235/api/tasks/${TASK_ID}/data" \
  -H "Authorization: Token $CVAT_TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Organization: Ploycube" \
  -d '{
    "cloud_storage_id": 4,
    "server_files": [
      "nrt_Vincennes/images/000bb7fa63264008.jpg",
      "nrt_Vincennes/images/000d05d4764b464e.jpg"
    ],
    "image_quality": 70,
    "use_zip_chunks": true,
    "use_cache": true,
    "sorting_method": "natural"
  }'
# Ответ: {"rq_id": "action=create&target=task&target_id=19"} (HTTP 202)

# Шаг 3: Отслеживать прогресс создания
curl -s "http://192.168.20.235/api/requests/action%3Dcreate%26target%3Dtask%26target_id%3D${TASK_ID}" \
  -H "Authorization: Token $CVAT_TOKEN" \
  -H "X-Organization: Ploycube"
# Ждать status=finished
```

**Полный пример: создание задачи из MinIO с помощью скрипта**

При большом количестве файлов (>500) CVAT UI обрезает список из-за пагинации. API решает эту проблему:

```bash
#!/bin/bash
# create-cvat-task.sh — создание задачи из MinIO Cloud Storage
CVAT_TOKEN="your-token-here"
CVAT_URL="http://192.168.20.235"
PROJECT_ID=4
SEGMENT_SIZE=1000
IMAGE_QUALITY=70
CLOUD_STORAGE_ID=4  # MinIO Datasets

MINIO_PREFIX="nrt_Vincennes-Athletic-small_2026-02-10_201919/images"
TASK_NAME="Vincennes-Athletic-small_2026-02-10_201919"

# 1. Получить список файлов из MinIO
echo "Listing files from MinIO..."
mcli ls "homelab/datasets/${MINIO_PREFIX}/" | awk '{print $NF}' > /tmp/files.txt
FILE_COUNT=$(wc -l < /tmp/files.txt)
echo "Found ${FILE_COUNT} files"

# 2. Создать задачу
TASK_ID=$(curl -s -X POST "${CVAT_URL}/api/tasks" \
  -H "Authorization: Token $CVAT_TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Organization: Ploycube" \
  -d "{
    \"name\": \"${TASK_NAME}\",
    \"project_id\": ${PROJECT_ID},
    \"segment_size\": ${SEGMENT_SIZE},
    \"source_storage\": {
      \"location\": \"cloud_storage\",
      \"cloud_storage_id\": ${CLOUD_STORAGE_ID}
    },
    \"target_storage\": {
      \"location\": \"cloud_storage\",
      \"cloud_storage_id\": 3
    }
  }" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
echo "Created task #${TASK_ID}"

# 3. Собрать JSON payload с server_files
python3 -c "
import json
prefix = '${MINIO_PREFIX}/'
with open('/tmp/files.txt') as f:
    files = [prefix + line.strip() for line in f if line.strip()]
payload = {
    'cloud_storage_id': ${CLOUD_STORAGE_ID},
    'server_files': files,
    'image_quality': ${IMAGE_QUALITY},
    'use_zip_chunks': True,
    'use_cache': True,
    'sorting_method': 'natural'
}
with open('/tmp/data_payload.json', 'w') as out:
    json.dump(payload, out)
print(f'Payload ready: {len(files)} files')
"

# 4. Отправить данные
curl -s -X POST "${CVAT_URL}/api/tasks/${TASK_ID}/data" \
  -H "Authorization: Token $CVAT_TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Organization: Ploycube" \
  -d @/tmp/data_payload.json
echo ""

# 5. Ждать завершения
RQ_ID="action%3Dcreate%26target%3Dtask%26target_id%3D${TASK_ID}"
while true; do
  STATUS=$(curl -s "${CVAT_URL}/api/requests/${RQ_ID}" \
    -H "Authorization: Token $CVAT_TOKEN" \
    -H "X-Organization: Ploycube" | python3 -c "import json,sys; print(json.load(sys.stdin)['status'])")
  echo "Status: ${STATUS}"
  [ "$STATUS" = "finished" ] && break
  [ "$STATUS" = "failed" ] && echo "FAILED!" && exit 1
  sleep 10
done

echo "Task #${TASK_ID} ready: ${CVAT_URL}/tasks/${TASK_ID}"
```

#### 4. Импорт YOLO-аннотаций

**ВАЖНО: Path matching для Cloud Storage задач**

При создании задачи из Cloud Storage, CVAT сохраняет полный путь изображения из bucket (включая prefix). Аннотации в YOLO-zip должны соответствовать этой структуре.

```
┌─────────────────────────────────────────────────────────────────┐
│            YOLO Annotation Path Matching                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   CVAT хранит image path:                                       │
│   polyvision-cls-4-v1.1.6/Centre-sportif/images/abc123.jpg     │
│                                                                  │
│   YOLO zip должен содержать:                                    │
│   ├── obj.names                                                  │
│   ├── obj.data                                                   │
│   ├── train.txt                                                  │
│   │   └─ data/obj_train_data/Centre-sportif/images/abc123.jpg  │
│   └── obj_train_data/                                            │
│       └── Centre-sportif/images/abc123.txt  ← аннотация        │
│                                                                  │
│   Ключ: путь в train.txt после "data/obj_train_data/"           │
│   должен совпадать с путём в CVAT после prefix.                 │
│                                                                  │
│   ❌ НЕ работает: obj_train_data/abc123.txt (плоский путь)      │
│   ✅ Работает: obj_train_data/Centre-sportif/images/abc123.txt  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Загрузка аннотаций:**

Если у задачи `source_storage=cloud_storage`, CVAT ищет файл аннотаций в Cloud Storage, а не в загруженных данных. Поэтому zip нужно сначала загрузить в MinIO:

```bash
# Загрузить zip в MinIO
mcli cp annotations.zip homelab/datasets/annotations.zip

# Импортировать, указав cloud_storage_id и filename
curl -s -X POST \
  "http://192.168.20.235/api/tasks/{task_id}/annotations?format=YOLO+1.1&filename=annotations.zip&location=cloud_storage&cloud_storage_id=4" \
  -H "Authorization: Token $CVAT_TOKEN" \
  -H "X-Organization: Ploycube"

# Отслеживать прогресс
curl -s "http://192.168.20.235/api/requests/action%3Dimport%26target%3Dtask%26target_id%3D{task_id}%26subresource%3Dannotations" \
  -H "Authorization: Token $CVAT_TOKEN" \
  -H "X-Organization: Ploycube"

# Удалить временный zip из MinIO после импорта
mcli rm homelab/datasets/annotations.zip
```

#### 5. Скрипт генерации YOLO-zip для импорта

```python
import os, glob, zipfile

def create_yolo_annotation_zip(
    annotation_dir: str,
    class_names: list[str],
    zip_path: str,
    minio_prefix: str = ""
):
    """
    Создать YOLO-zip для импорта в CVAT.

    Args:
        annotation_dir: Директория с .txt аннотациями (рекурсивный поиск)
        class_names: Список классов в порядке ID
        zip_path: Путь для выходного zip
        minio_prefix: Prefix пути в MinIO (для train.txt)
                       Если пусто — используются плоские имена файлов
    """
    train_lines = []
    ann_files = {}

    for txt in glob.glob(os.path.join(annotation_dir, '**', '*.txt'), recursive=True):
        with open(txt) as f:
            content = f.read().strip()
        if not content:
            continue

        rel = os.path.relpath(txt, annotation_dir)
        ann_zip_path = f'obj_train_data/{rel}'
        train_lines.append(f'data/obj_train_data/{rel.replace(".txt", ".jpg")}')
        ann_files[ann_zip_path] = content

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('obj.names', '\n'.join(class_names) + '\n')
        zf.writestr('obj.data',
            f'classes = {len(class_names)}\n'
            'train = data/train.txt\n'
            'names = data/obj.names\n'
            'backup = backup/\n')
        zf.writestr('train.txt', '\n'.join(sorted(train_lines)) + '\n')
        for path, content in sorted(ann_files.items()):
            zf.writestr(path, content + '\n')

    print(f'Created {zip_path}: {len(ann_files)} annotations, '
          f'{len(class_names)} classes')

# Пример использования
create_yolo_annotation_zip(
    annotation_dir='/path/to/obj_Train_data',
    class_names=['ball', 'player', 'side_referee', 'main_referee'],
    zip_path='/tmp/annotations.zip'
)
```

### Структура данных в MinIO

```
MinIO (192.168.20.237)
│
├── datasets/                              ← Source Storage
│   ├── polyvision-cls-4-v1.1.6/          ← Текущий датасет (4 класса)
│   │   ├── Centre-sportif-Max-Rousie-Match-24-01-2026/
│   │   │   └── images/                    ← 853 изображения + аннотации
│   │   ├── nrt_Maryse-Hilsz-Sports-Center_2026-02-04_214315/
│   │   │   └── images/                    ← 251 изображение + аннотации
│   │   └── polyvision-cls-5-v1.1/
│   │       └── images/Train/              ← 391 изображение + аннотации
│   │
│   ├── polyvision-cls-5-v1.1/            ← Исходный датасет (5 классов)
│   │   └── Polyvision_dataset_five_classes_v1.1/
│   │       ├── data.yaml
│   │       ├── Train.txt / Validation.txt
│   │       ├── images/ (Train/, Validation/)
│   │       └── labels/ (Train/, Validation/)
│   │
│   ├── nrt_Centre-sportif-Max-Rousie_2026-01-28_111531/
│   ├── nrt_Maryse-Hilsz-Sports-Center_2026-02-04_214315/
│   └── nrt_Vincennes-Athletic-2025-11-23_13-49-20_2026-02-05_134351/
│
├── cvat/                                  ← Target Storage
│   ├── exports/
│   │   └── polyvision/
│   │       ├── polyvision_yolo_2026-01-22.zip
│   │       ├── polyvision_coco_2026-01-22.zip
│   │       └── polyvision_cvat_2026-01-22.zip
│   └── backups/
│       ├── polyvision_v1_backup_2026-01-22.zip
│       └── polyvision_v2_backup_2026-01-23.zip
│
├── clearml/                               ← ClearML артефакты
│   └── ...
│
└── models/                                ← Обученные модели
    └── ...
```

### Автоматизация бэкапов (опционально)

CVAT не имеет встроенного автобэкапа. Можно настроить через Kubernetes CronJob:

```yaml
# cvat-backup-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: cvat-auto-backup
  namespace: cvat
spec:
  schedule: "0 3 * * *"  # Ежедневно в 03:00
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: python:3.11-slim
            env:
            - name: CVAT_HOST
              value: "http://cvat-backend-service:8080"
            - name: CVAT_TOKEN
              valueFrom:
                secretKeyRef:
                  name: cvat-api-credentials
                  key: token
            command:
            - python3
            - -c
            - |
              import requests
              import os
              from datetime import datetime

              host = os.environ['CVAT_HOST']
              token = os.environ['CVAT_TOKEN']
              headers = {'Authorization': f'Token {token}'}

              # Получить список проектов
              projects = requests.get(f'{host}/api/projects', headers=headers).json()

              for project in projects.get('results', []):
                  pid = project['id']
                  name = project['name'].replace(' ', '_')
                  date = datetime.now().strftime('%Y%m%d')

                  # Запустить backup
                  requests.post(
                      f'{host}/api/projects/{pid}/backup',
                      headers=headers,
                      json={
                          'filename': f'{name}_auto_{date}',
                          'target_storage': {'location': 'cloud_storage', 'cloud_storage_id': 3}  # MinIO CVAT Internal
                      }
                  )
                  print(f'Backup started for project: {name}')
          restartPolicy: OnFailure
```

**Создать secret с API токеном:**
```bash
# Получить токен в CVAT UI: User → Settings → Account → Access token
kubectl create secret generic cvat-api-credentials \
  --from-literal=token=YOUR_API_TOKEN \
  -n cvat
```

### Интеграция с ClearML

Датасеты в MinIO доступны как для CVAT, так и для ClearML:

```python
from clearml import Dataset

# Зарегистрировать датасет из MinIO
dataset = Dataset.create(
    dataset_name="polyvision_football",
    dataset_project="Polyvision",
    dataset_version="1.1"
)

# Добавить файлы из того же MinIO bucket
dataset.add_external_files(
    source_url="s3://192.168.20.237:80/datasets/polyvision-cls-5-v1.1/",
    wildcard="**/*"
)

dataset.finalize(auto_upload=True)
```

Workflow CVAT ↔ ClearML:
1. **CVAT**: Аннотирование в `s3://datasets/`
2. **CVAT**: Export в `s3://cvat/exports/`
3. **ClearML**: Регистрация датасета из `s3://datasets/`
4. **ClearML**: Обучение модели → результат в `s3://models/`
5. **CVAT/Nuclio**: Использование модели для авто-аннотации

### Ссылки

- [CVAT Backup Documentation](https://docs.cvat.ai/docs/dataset_management/backup/)
- [CVAT Attach Cloud Storage](https://docs.cvat.ai/docs/manual/basics/attach-cloud-storage/)
- [Source & Target Storage PR #4842](https://github.com/cvat-ai/cvat/pull/4842)

---

## Nuclio — Serverless AI Functions

Nuclio — serverless платформа для запуска AI моделей, интегрированная с CVAT для автоматической аннотации.

### Теория: Что такое Nuclio

**Nuclio** — высокопроизводительная serverless платформа для data science и ML workloads.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Nuclio + CVAT Architecture                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   CVAT UI                                                        │
│      │                                                           │
│      │ "Auto-annotate with YOLO"                                │
│      ▼                                                           │
│   ┌──────────────┐                                              │
│   │ CVAT Backend │                                              │
│   └──────┬───────┘                                              │
│          │ HTTP request (image data)                            │
│          ▼                                                       │
│   ┌──────────────────────────────────────────────┐              │
│   │              Nuclio Platform                  │              │
│   │  ┌────────────────────────────────────────┐  │              │
│   │  │           Function Pod                  │  │              │
│   │  │  ┌──────────────────────────────────┐  │  │              │
│   │  │  │     AI Model (YOLO, SAM, etc)    │  │  │              │
│   │  │  │  - Load model weights            │  │  │              │
│   │  │  │  - Process image                 │  │  │              │
│   │  │  │  - Return annotations            │  │  │              │
│   │  │  └──────────────────────────────────┘  │  │              │
│   │  └────────────────────────────────────────┘  │              │
│   └──────────────────────────────────────────────┘              │
│          │                                                       │
│          │ JSON response (bounding boxes, masks)                │
│          ▼                                                       │
│   CVAT UI показывает аннотации                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Зачем Nuclio:**

| Преимущество | Описание |
|--------------|----------|
| **Auto-scaling** | Функции масштабируются от 0 до N реплик |
| **GPU support** | Нативная поддержка NVIDIA GPU |
| **Hot reload** | Модель загружается один раз, inference быстрый |
| **Isolation** | Каждая модель в своём контейнере |
| **REST API** | Простой HTTP интерфейс для inference |

**Компоненты Nuclio:**

| Компонент | Назначение |
|-----------|------------|
| **nuclio-controller** | Управляет жизненным циклом функций |
| **nuclio-dashboard** | Web UI для деплоя функций |
| **Function pods** | Контейнеры с AI моделями |

### Как Nuclio строит функции

```
┌─────────────────────────────────────────────────────────────────┐
│                    Function Build Process                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   1. User deploys function.yaml                                 │
│          │                                                       │
│          ▼                                                       │
│   2. Nuclio Dashboard получает spec                             │
│          │                                                       │
│          ▼                                                       │
│   3. Kaniko (in-cluster builder) собирает Docker image          │
│      - Base image (python, pytorch)                             │
│      - Dependencies (requirements.txt)                          │
│      - Model weights                                            │
│      - Handler code                                             │
│          │                                                       │
│          ▼                                                       │
│   4. Push image в Registry (Docker Hub, Harbor)                 │
│          │                                                       │
│          ▼                                                       │
│   5. Nuclio создаёт Deployment + Service                        │
│          │                                                       │
│          ▼                                                       │
│   6. Function ready для inference                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Kaniko** — tool для сборки Docker images внутри Kubernetes (без Docker daemon).

### Установка Nuclio

#### 1. Подготовка Container Registry

Nuclio требует registry для хранения собранных images. Варианты:

| Registry | Плюсы | Минусы |
|----------|-------|--------|
| **Docker Hub** | Бесплатно, просто | Rate limits, публичные images |
| **Harbor** | Self-hosted, приватный | Нужно разворачивать |
| **GitHub Container Registry** | Бесплатно для public repos | Нужен GitHub account |

**Для Docker Hub:**

```bash
# Создать access token на https://hub.docker.com/settings/security
# Scope: Read, Write, Delete
```

#### 2. Обновить values.yaml

```yaml
nuclio:
  enabled: true
  dashboard:
    containerBuilderKind: kaniko  # Сборка внутри K8s
  registry:
    loginUrl: docker.io
    credentials:
      username: your-dockerhub-username
      password: your-dockerhub-token  # Access Token, не пароль!
```

**Разбор параметров:**

| Параметр | Описание |
|----------|----------|
| `containerBuilderKind: kaniko` | Использовать Kaniko вместо Docker |
| `loginUrl` | URL registry (docker.io для Docker Hub) |
| `credentials` | Логин/токен для push images |

#### 3. Upgrade Helm release

```bash
helm upgrade cvat /path/to/helm-chart \
  --namespace cvat \
  -f cvat-values.yaml
```

#### 4. Проверка

```bash
# Nuclio поды
kubectl get pods -n cvat -l nuclio.io/app=dashboard
kubectl get pods -n cvat -l nuclio.io/app=controller

# Nuclio Dashboard
kubectl port-forward svc/cvat-nuclio-dashboard 8070:8070 -n cvat
# Открыть http://localhost:8070
```

### Деплой AI функции

#### Структура функции CVAT

```
serverless/
├── pytorch/
│   └── yolov5/
│       ├── function.yaml      # Nuclio spec
│       ├── function-gpu.yaml  # GPU версия
│       ├── main.py            # Handler code
│       └── requirements.txt   # Python dependencies
```

#### Пример function.yaml

```yaml
metadata:
  name: pth-yolov5
  namespace: cvat
  annotations:
    name: YOLOv5
    type: detector
    framework: pytorch
    spec: |
      [
        {"id": 0, "name": "person"},
        {"id": 1, "name": "car"},
        ...
      ]

spec:
  description: YOLOv5 object detection
  runtime: python:3.8
  handler: main:handler
  eventTimeout: 30s

  build:
    image: docker.io/your-user/cvat-yolov5:latest
    baseImage: ultralytics/yolov5:latest
    commands:
      - pip install -r requirements.txt

  triggers:
    default-http:
      kind: http
      workerAvailabilityTimeoutMilliseconds: 10000
      attributes:
        maxRequestBodySize: 33554432  # 32MB

  resources:
    limits:
      cpu: 2
      memory: 4Gi
    requests:
      cpu: 1
      memory: 2Gi

  platform:
    attributes:
      restartPolicy:
        name: always
        maximumRetryCount: 3
```

**Разбор spec:**

| Поле | Описание |
|------|----------|
| `metadata.annotations.type` | Тип модели: `detector`, `interactor`, `tracker` |
| `metadata.annotations.spec` | Классы которые модель детектирует |
| `spec.runtime` | Python версия |
| `spec.handler` | Точка входа (файл:функция) |
| `spec.build.image` | Куда push собранный image |
| `spec.build.baseImage` | Базовый образ |
| `spec.triggers` | HTTP endpoint настройки |
| `spec.resources` | CPU/Memory limits |

#### Деплой через nuctl

```bash
# Установить nuctl CLI
curl -s https://api.github.com/repos/nuclio/nuclio/releases/latest \
  | grep -i "browser_download_url.*nuctl.*linux.*amd64" \
  | cut -d '"' -f 4 \
  | xargs curl -Lo nuctl && chmod +x nuctl && sudo mv nuctl /usr/local/bin/

# Деплой функции
nuctl deploy --path /path/to/serverless/pytorch/yolov5 \
  --namespace cvat \
  --platform kube \
  --registry docker.io/your-user
```

#### Готовые модели CVAT

CVAT предоставляет готовые функции в репозитории `/home/edvin/Expirements/cvat/serverless/`:

| Модель | Framework | Тип | Описание |
|--------|-----------|-----|----------|
| **SAM** | PyTorch | interactor | Segment Anything (Meta) — интерактивная сегментация |
| **RetinaNet R101** | PyTorch | detector | Detectron2 object detection |
| **SiamMask** | PyTorch | tracker | Video object tracking |
| **TransT** | PyTorch | tracker | Transformer-based tracker |
| **HRNet32** | PyTorch | detector | Human pose estimation (mmpose) |
| **IOG** | PyTorch | interactor | Inside-Outside Guidance segmentation |
| **YOLOv7** | ONNX | detector | Fast object detection |
| **YOLOv3** | OpenVINO | detector | Object detection (Intel optimized) |
| **Faster R-CNN** | OpenVINO/TF | detector | Two-stage object detection |
| **Mask R-CNN** | OpenVINO | detector | Instance segmentation |
| **DEXTR** | OpenVINO | interactor | Deep Extreme Cut (4-click segmentation) |
| **Face Detection** | OpenVINO | detector | Intel face detection model |
| **Text Detection** | OpenVINO | detector | Text in images detection |
| **Semantic Segmentation** | OpenVINO | detector | Road scene segmentation (ADAS) |

**Типы моделей:**

| Тип | Описание | Использование |
|-----|----------|---------------|
| **detector** | Автоматическое обнаружение объектов | Нажать "Annotate" — модель найдёт все объекты |
| **interactor** | Интерактивная сегментация | Кликнуть на объект — модель выделит его маску |
| **tracker** | Трекинг в видео | Разметить объект на 1 кадре — трекер найдёт его на остальных |

#### Деплой моделей

```bash
cd /home/edvin/Expirements/cvat

# Посмотреть доступные модели
find serverless -name "function.yaml" -exec dirname {} \;

# Деплой SAM (Segment Anything) — лучший interactor
nuctl deploy --project-name cvat \
  --path serverless/pytorch/facebookresearch/sam/nuclio \
  --namespace cvat \
  --platform kube

# Деплой YOLOv7 (ONNX) — быстрый detector
nuctl deploy --project-name cvat \
  --path serverless/onnx/WongKinYiu/yolov7/nuclio \
  --namespace cvat \
  --platform kube

# Деплой SiamMask — tracker для видео
nuctl deploy --project-name cvat \
  --path serverless/pytorch/foolwood/siammask/nuclio \
  --namespace cvat \
  --platform kube
```

**Рекомендация:** Начать с SAM (interactor) + YOLOv7 (detector) — покрывает большинство задач.

### GPU функции

Для inference на GPU (например, на [[polydev-desktop]]):

#### 1. Изменить function.yaml

```yaml
spec:
  resources:
    limits:
      nvidia.com/gpu: 1  # Запросить 1 GPU
      memory: 8Gi
    requests:
      nvidia.com/gpu: 1
      memory: 4Gi

  # Указать GPU RuntimeClass
  platform:
    attributes:
      runtimeClassName: nvidia  # K3s NVIDIA RuntimeClass
```

#### 2. Добавить tolerations (если GPU нода имеет taints)

```yaml
spec:
  platform:
    attributes:
      tolerations:
        - key: "nvidia.com/gpu"
          operator: "Exists"
          effect: "NoSchedule"
```

#### 3. Деплой

```bash
nuctl deploy --path serverless/pytorch/yolov5 \
  --namespace cvat \
  --platform kube \
  --resource-limit nvidia.com/gpu=1
```

### Использование в CVAT UI

1. Открыть задачу (Task) в CVAT
2. Перейти в режим аннотации (Jobs → Open)
3. В меню выбрать **AI Tools** или **Magic Wand**
4. Выбрать модель из списка (например, YOLOv5)
5. Нажать **Annotate** — модель обработает кадр
6. Проверить и скорректировать результат

### Мониторинг функций

```bash
# Список функций
nuctl get functions --namespace cvat

# Логи функции
nuctl logs pth-yolov5 --namespace cvat

# Статистика
kubectl get pods -n cvat -l nuclio.io/function-name=pth-yolov5

# Invoke функцию напрямую (для теста)
nuctl invoke pth-yolov5 --namespace cvat \
  --method POST \
  --body '{"image": "base64_encoded_image"}'
```

### Troubleshooting Nuclio

#### Function stuck в Building

```bash
# Проверить Kaniko pod
kubectl get pods -n cvat -l nuclio.io/function-name=<func-name>
kubectl logs -n cvat -l nuclio.io/function-build

# Частые причины:
# - Неправильные credentials registry
# - Rate limit Docker Hub
# - Ошибка в requirements.txt
```

#### Function CrashLoopBackOff

```bash
# Логи функции
kubectl logs -n cvat -l nuclio.io/function-name=<func-name>

# Частые причины:
# - Не хватает памяти (увеличить resources.limits.memory)
# - Ошибка загрузки модели
# - Неправильный handler
```

#### Функция в состоянии Error / "Fetching inference status"

**Симптом:** В CVAT UI постоянно появляется уведомление:
```
Fetching inference status for the ...
Open the Browser Console to get details
```

**Причина:** CVAT периодически опрашивает Nuclio API (`GET /api/functions`). Если любая функция в состоянии `error` (например, неудачный билд Docker-образа), CVAT показывает уведомление — даже если эта функция не используется.

**Диагностика:**

```bash
# Проверить статус всех функций
curl -s http://192.168.20.236/api/functions | python3 -c "
import json,sys
for name, fn in json.load(sys.stdin).items():
    state = fn.get('status',{}).get('state','?')
    msg = fn.get('status',{}).get('message','')
    print(f'{name}: {state}')
    if msg: print(f'  error: {msg[:200]}')
"

# Проверить есть ли pod для функции
kubectl get pods -n cvat -l nuclio.io/function-name=<func-name>
```

**Решение — удалить нерабочую функцию через API:**

```bash
# Удалить функцию через Nuclio Dashboard API
curl -s -X DELETE "http://192.168.20.236/api/functions" \
  -H "Content-Type: application/json" \
  -d '{"metadata": {"name": "onnx-wongkinyiu-yolov7", "namespace": "cvat"}}'
# HTTP 204 — успешно удалено

# Проверить что осталось
curl -s http://192.168.20.236/api/functions | python3 -c "
import json,sys
for name, fn in json.load(sys.stdin).items():
    print(f'{name}: {fn[\"status\"][\"state\"]}')
"
```

> **Примечание:** Если функция нужна, но билд упал — исправьте `function.yaml` и задеплойте заново через `nuctl deploy`.

#### GPU не используется

```bash
# Проверить что GPU нода видна
kubectl get nodes -l nvidia.com/gpu=true

# Проверить RuntimeClass
kubectl get runtimeclass nvidia

# Проверить что функция запросила GPU
kubectl describe pod -n cvat -l nuclio.io/function-name=<func-name> | grep nvidia
```

#### Модели не отображаются в CVAT UI после изменений

**Симптом:** После обновления CVAT или изменения конфигурации (Smokescreen, Ingress и т.д.) модели Nuclio перестают отображаться в CVAT UI (AI Tools → пустой список).

**Причина:** CVAT backend не может подключиться к Nuclio Dashboard. Типичные причины:

1. **Неправильный порт:** CVAT по умолчанию ожидает Nuclio на порту 8070, но Helm chart CVAT создаёт сервис на порту 80
2. **Неправильный hostname:** `CVAT_NUCLIO_HOST` указывает на несуществующий сервис
3. **Network policy:** Сетевые политики блокируют трафик между CVAT и Nuclio

**Диагностика:**

```bash
# 1. Проверить что Nuclio Dashboard работает
kubectl get pods -n cvat | grep nuclio
# nuclio-controller и nuclio-dashboard должны быть Running

# 2. Проверить сервис Nuclio
kubectl get svc -n cvat | grep nuclio
# cvat-nuclio-dashboard должен показывать порт (обычно 80)

# 3. Проверить текущее значение CVAT_NUCLIO_HOST
kubectl exec -n cvat deploy/cvat-backend-server -- env | grep NUCLIO

# 4. Проверить доступность Nuclio API из CVAT backend
kubectl exec -n cvat deploy/cvat-backend-server -- \
  curl -s http://cvat-nuclio-dashboard:80/api/functions | head -c 200

# Если возвращает JSON с функциями — проблема в CVAT_NUCLIO_HOST
# Если ошибка подключения — проверить сервис и поды
```

**Решение:**

```bash
# Узнать правильный порт сервиса Nuclio Dashboard
kubectl get svc cvat-nuclio-dashboard -n cvat -o jsonpath='{.spec.ports[0].port}'
# Обычно: 80 (не 8070!)

# ВАЖНО: CVAT использует ОТДЕЛЬНЫЕ переменные для host и port
# НЕ указывать порт в CVAT_NUCLIO_HOST — иначе получится двойной порт!

# Обновить ВСЕ компоненты которые обращаются к Nuclio:
# - backend-server: для отображения списка моделей в UI
# - worker-annotation: для выполнения автоматической аннотации
kubectl set env deploy/cvat-backend-server -n cvat \
  CVAT_NUCLIO_HOST="cvat-nuclio-dashboard" \
  CVAT_NUCLIO_PORT="80"

kubectl set env deploy/cvat-backend-worker-annotation -n cvat \
  CVAT_NUCLIO_HOST="cvat-nuclio-dashboard" \
  CVAT_NUCLIO_PORT="80"

# Дождаться перезапуска
kubectl rollout status deploy/cvat-backend-server -n cvat
kubectl rollout status deploy/cvat-backend-worker-annotation -n cvat

# Проверить что модели теперь доступны
kubectl exec -n cvat deploy/cvat-backend-server -- \
  curl -s http://cvat-nuclio-dashboard:80/api/functions | python3 -c "import sys,json; print('\n'.join(json.load(sys.stdin).keys()))"
```

**Через Helm (постоянное решение):**

```yaml
# cvat-values.yaml
cvat:
  backend:
    server:
      envs:
        CVAT_NUCLIO_HOST: "cvat-nuclio-dashboard"
        CVAT_NUCLIO_PORT: "80"
    worker:
      annotation:
        envs:
          CVAT_NUCLIO_HOST: "cvat-nuclio-dashboard"
          CVAT_NUCLIO_PORT: "80"
```

**Разбор проблемы:**

CVAT формирует URL к Nuclio как `http://{CVAT_NUCLIO_HOST}:{CVAT_NUCLIO_PORT}/api/functions`.

```
┌─────────────────────────────────────────────────────────────────┐
│              Nuclio Connectivity Issue                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ❌ Неправильно (двойной порт):                                │
│   CVAT_NUCLIO_HOST=cvat-nuclio-dashboard:80                     │
│   CVAT_NUCLIO_PORT=8070 (default)                               │
│   URL: http://cvat-nuclio-dashboard:80:8070  ← Ошибка парсинга │
│                                                                  │
│   ❌ Неправильно (дефолтный порт):                              │
│   CVAT_NUCLIO_HOST=cvat-nuclio-dashboard                        │
│   CVAT_NUCLIO_PORT=8070 (default)                               │
│   URL: http://cvat-nuclio-dashboard:8070    ← Connection refused│
│                                                                  │
│   ✅ Правильно:                                                  │
│   CVAT_NUCLIO_HOST=cvat-nuclio-dashboard                        │
│   CVAT_NUCLIO_PORT=80                                           │
│   URL: http://cvat-nuclio-dashboard:80      ← Работает!        │
│                                                                  │
│   Kubernetes Service mapping:                                    │
│   cvat-nuclio-dashboard:80 ──► nuclio-dashboard pod:8070       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Проверка после исправления:**

1. Открыть CVAT UI: http://192.168.20.235
2. Перейти в любую задачу → Jobs → Open
3. Нажать на иконку AI Tools (волшебная палочка)
4. Должен появиться список моделей (YOLOv7, YOLOv11, etc.)

#### Автоаннотация: "Invocation URL is required"

**Симптом:** Модели отображаются в списке, но при запуске автоаннотации ошибка:
```
Automatic annotation failed
500 Server Error: Internal Server Error
```

В логах Nuclio Dashboard:
```
Failed to invoke function
err: "Failed to resolve invocation url"
"Invocation URL is required"
X-Nuclio-Invoke-Via: "domain-name"
```

**Причина:** CVAT использует `x-nuclio-invoke-via: domain-name` при вызове функций через Nuclio Dashboard. Это означает, что Dashboard должен знать URL функции для проксирования запроса. Если функция не имеет `internalInvocationUrls` или `externalInvocationUrls`, Dashboard не может её вызвать.

```
┌─────────────────────────────────────────────────────────────────┐
│            Function Invocation URL Problem                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   CVAT Worker                                                    │
│       │                                                          │
│       │ POST /api/function_invocations                          │
│       │ X-Nuclio-Function-Name: yolo11x-cvat-detector-gpu       │
│       │ X-Nuclio-Invoke-Via: domain-name                        │
│       ▼                                                          │
│   ┌────────────────────┐                                        │
│   │ Nuclio Dashboard   │                                        │
│   │                    │                                        │
│   │ 1. Lookup function │                                        │
│   │ 2. Get invocation  │  ← Если internalInvocationUrls = None │
│   │    URL             │     → "Invocation URL is required"     │
│   │ 3. Proxy request   │                                        │
│   └────────────────────┘                                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Диагностика:**

```bash
# Проверить invocation URLs функции
kubectl exec -n cvat deploy/cvat-backend-server -- \
  curl -s http://cvat-nuclio-dashboard:80/api/functions/yolo11x-cvat-detector-gpu | \
  python3 -c "import sys,json; d=json.load(sys.stdin); \
    print('httpPort:', d.get('status',{}).get('httpPort')); \
    print('externalIP:', d.get('status',{}).get('externalInvocationUrls')); \
    print('internalIP:', d.get('status',{}).get('internalInvocationUrls'))"

# Если internalIP = None — проблема в конфигурации функции
```

**Решение:**

Проблема возникает когда функция была создана с кастомным портом в triggers или без `serviceType: ClusterIP`. Нужно пересоздать функцию с правильной конфигурацией.

**1. Исправить function.yaml:**

```yaml
# НЕПРАВИЛЬНО (кастомный порт, нет serviceType):
triggers:
  myHttpTrigger:
    kind: http
    attributes:
      maxRequestBodySize: 33554432
      port: 38888  # ← Убрать!

# ПРАВИЛЬНО:
triggers:
  myHttpTrigger:
    kind: http
    attributes:
      maxRequestBodySize: 33554432
      serviceType: ClusterIP  # ← Добавить!
```

**2. Пересоздать функцию:**

```bash
# Удалить старую функцию
nuctl delete function yolo11x-cvat-detector-gpu --namespace cvat --platform kube

# Задеплоить заново
nuctl deploy --project-name cvat \
  --path /path/to/serverless/custom/nuclio \
  --namespace cvat \
  --platform kube \
  --registry docker.io/your-user

# Ожидаемый вывод:
# "internalInvocationURLs": ["nuclio-yolo11x-cvat-detector-gpu.cvat.svc.cluster.local:8080"]
```

**3. Проверить:**

```bash
# После деплоя должен появиться internal URL
kubectl get nucliofunctions yolo11x-cvat-detector-gpu -n cvat \
  -o jsonpath='{.status.internalInvocationUrls}'
# Ожидаемо: ["nuclio-yolo11x-cvat-detector-gpu.cvat.svc.cluster.local:8080"]
```

**Устойчивость к рестарту:**

Все настройки сохраняются в Kubernetes объектах:
- `CVAT_NUCLIO_*` переменные сохранены в Deployment spec
- NuclioFunction CRD сохраняет конфигурацию функции
- При рестарте кластера всё восстановится автоматически

#### GPU функция работает на CPU (torch.cuda.is_available() = False)

**Симптом:** Функция с `nvidia.com/gpu: 1` запущена, но PyTorch не видит GPU:
```bash
kubectl exec -n cvat <pod> -- python3 -c "import torch; print(torch.cuda.is_available())"
# CUDA available: False
```

**Причина:** Nuclio controller **не передаёт** `runtimeClassName` из function.yaml в Deployment template. Даже если указано:
```yaml
platform:
  attributes:
    runtimeClassName: nvidia
```

Nuclio сохраняет это в NuclioFunction CRD, но при создании Deployment не включает `runtimeClassName` в pod spec. В результате:
- GPU "выделен" на уровне Kubernetes scheduler (pod запущен на GPU ноде)
- Но контейнер использует обычный `runc` вместо `nvidia-container-runtime`
- PyTorch не может обращаться к GPU драйверам

```
┌─────────────────────────────────────────────────────────────────┐
│            RuntimeClass Problem in Nuclio                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   function.yaml                                                  │
│       │                                                          │
│       │ runtimeClassName: nvidia                                 │
│       ▼                                                          │
│   ┌────────────────────┐                                        │
│   │ NuclioFunction CRD │  ← runtimeClassName сохранён           │
│   └─────────┬──────────┘                                        │
│             │                                                    │
│             │ Nuclio Controller                                  │
│             ▼                                                    │
│   ┌────────────────────┐                                        │
│   │    Deployment      │  ← runtimeClassName НЕ передан! ❌     │
│   │  (no runtimeClass) │                                        │
│   └─────────┬──────────┘                                        │
│             │                                                    │
│             ▼                                                    │
│   ┌────────────────────┐                                        │
│   │       Pod          │  ← Использует runc вместо nvidia       │
│   │ CUDA: False        │                                        │
│   └────────────────────┘                                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Диагностика:**

```bash
# Проверить runtimeClassName в NuclioFunction (есть)
kubectl get nucliofunctions <func-name> -n cvat -o yaml | grep runtimeClassName
# runtimeClassName: nvidia

# Проверить runtimeClassName в Deployment (пусто)
kubectl get deployment nuclio-<func-name> -n cvat \
  -o jsonpath='{.spec.template.spec.runtimeClassName}'
# (пустой вывод)

# Проверить CUDA в контейнере
kubectl exec -n cvat <pod> -- python3 -c "import torch; print('CUDA:', torch.cuda.is_available())"
# CUDA: False
```

**Решение — патч Deployment:**

```bash
# Добавить runtimeClassName в deployment
kubectl patch deployment nuclio-<func-name> -n cvat \
  --type='json' \
  -p='[{"op": "add", "path": "/spec/template/spec/runtimeClassName", "value": "nvidia"}]'

# Дождаться rollout
kubectl rollout status deployment nuclio-<func-name> -n cvat

# Проверить GPU
POD=$(kubectl get pods -n cvat -l nuclio.io/function-name=<func-name> -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n cvat $POD -- python3 -c "import torch; print('CUDA:', torch.cuda.is_available()); print('Device:', torch.cuda.get_device_name(0))"
# CUDA: True
# Device: NVIDIA RTX A6000
```

**Автоматизация:**

Патч нужно применять после каждого `nuctl deploy`. Варианты автоматизации:

1. **Bash-скрипт обёртка** — запускать вместо `nuctl deploy`:
```bash
#!/bin/bash
# deploy-gpu-function.sh
FUNC_NAME=$1
NAMESPACE=${2:-cvat}

nuctl deploy --project-name cvat \
  --path "$PWD" \
  --namespace "$NAMESPACE" \
  --platform kube \
  --registry docker.io/edvin3i

# Ждём пока функция станет ready
echo "Waiting for function to be ready..."
sleep 10

# Патчим deployment
kubectl patch deployment "nuclio-$FUNC_NAME" -n "$NAMESPACE" \
  --type='json' \
  -p='[{"op": "add", "path": "/spec/template/spec/runtimeClassName", "value": "nvidia"}]'

kubectl rollout status deployment "nuclio-$FUNC_NAME" -n "$NAMESPACE"
echo "GPU function deployed successfully!"
```

2. **Kyverno Policy** — автоматически мутирует все deployments с `nvidia.com/gpu`:
```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: add-nvidia-runtime-class
spec:
  rules:
  - name: add-runtime-class-to-gpu-pods
    match:
      resources:
        kinds:
        - Deployment
        namespaces:
        - cvat
    mutate:
      patchStrategicMerge:
        spec:
          template:
            spec:
              runtimeClassName: nvidia
    preconditions:
      all:
      - key: "{{ request.object.spec.template.spec.containers[0].resources.limits.\"nvidia.com/gpu\" || '' }}"
        operator: GreaterThan
        value: "0"
```

3. **Mutating Webhook** — кастомный webhook для полного контроля

**Рекомендация:** Использовать bash-скрипт для простоты или Kyverno для полной автоматизации.

> Подробное сравнение Policy Engines и обоснование выбора Kyverno: [[Kubernetes - Policy Engines]]

#### KVRocks PVC заполнен (No space left on device)

**Симптом:** CVAT перестаёт работать, в логах Redis/KVRocks:
```
redis.exceptions.ResponseError: IO error: No space left on device:
While appending to file: /var/lib/kvrocks/db/000514.log: No space left on device
```

**Причина:** PVC для KVRocks (20Gi по умолчанию) заполняется SST файлами RocksDB и архивными WAL логами. Архивные WAL логи в `/var/lib/kvrocks/db/archive/` — это уже записанные в SST данные, которые KVRocks хранит на случай восстановления.

**Теория:** KVRocks — key-value БД на основе RocksDB, которую CVAT использует вместо Redis для хранения кэша аннотаций и метаданных. RocksDB записывает данные сначала в WAL (Write-Ahead Log), затем компактирует в SST файлы. Архивные WAL (`archive/`) безопасно удалять — они уже компактированы.

**Диагностика:**

```bash
# Проверить заполненность PVC
kubectl exec -i cvat-kvrocks-0 -n cvat -- df -h /var/lib/kvrocks/db

# Проверить размер архива (используй -i без -t, иначе kubectl panic)
kubectl exec -i cvat-kvrocks-0 -n cvat -- sh -c 'du -sh /var/lib/kvrocks/db/archive'

# Посмотреть общее распределение
kubectl exec -i cvat-kvrocks-0 -n cvat -- sh -c 'du -sh /var/lib/kvrocks/db/*'
```

**Быстрое решение — очистить архив WAL:**

```bash
# Удалить архивные WAL логи (безопасно — данные уже в SST)
kubectl exec -i cvat-kvrocks-0 -n cvat -- sh -c 'rm -rf /var/lib/kvrocks/db/archive/*'

# Проверить освобождённое место
kubectl exec -i cvat-kvrocks-0 -n cvat -- df -h /var/lib/kvrocks/db
```

**Долгосрочное решение — расширить PVC через Longhorn:**

```bash
# Проверить имя PVC
kubectl get pvc -n cvat | grep kvrocks
# cvat-kvrocks-data-cvat-kvrocks-0

# Проверить что StorageClass разрешает расширение
kubectl get storageclass longhorn -o yaml | grep allowVolumeExpansion
# Если false:
# kubectl patch storageclass longhorn -p '{"allowVolumeExpansion": true}'

# Расширить PVC (Longhorn admission webhook проверяет доступное место на диске ноды)
kubectl patch pvc cvat-kvrocks-data-cvat-kvrocks-0 -n cvat \
  -p '{"spec":{"resources":{"requests":{"storage":"30Gi"}}}}'

# Если ошибка "cannot schedule N more bytes to disk" — на ноде не хватает места
# для реплик. Workaround: временно уменьшить numberOfReplicas до 1, удалив
# реплики с тесных нод, расширить PVC, затем вернуть реплики.
#
# Проверить headroom на нодах:
# kubectl get nodes.longhorn.io -n longhorn-system -o json | python3 -c "..."
#
# Уменьшить реплики (оставить только polydev-desktop):
# VOLUME=pvc-b6631e93-4992-4683-a04c-25bb748fa564
# kubectl patch volume $VOLUME -n longhorn-system --type merge \
#   -p '{"spec":{"numberOfReplicas":1}}'
# kubectl delete replicas.longhorn.io <replica-name> -n longhorn-system
#
# После расширения — вернуть реплики:
# kubectl patch volume $VOLUME -n longhorn-system --type merge \
#   -p '{"spec":{"numberOfReplicas":2}}'

# После расширения PVC — рестарт pod для подхвата нового размера ФС
kubectl delete pod cvat-kvrocks-0 -n cvat
# StatefulSet пересоздаст pod автоматически

# Проверить новый размер
kubectl exec -i cvat-kvrocks-0 -n cvat -- df -h /var/lib/kvrocks/db
```

**Радикальное решение — очистить image cache (FLUSHDB + COMPACT):**

Если архив WAL маленький, а место занимают SST файлы (закэшированные image chunks) — нужно сбросить кэш целиком. CVAT перезагрузит изображения из MinIO по запросу.

```bash
# Проверить количество и размер SST файлов
kubectl exec -i cvat-kvrocks-0 -n cvat -- sh -c 'ls /var/lib/kvrocks/db/*.sst | wc -l'
kubectl exec -i cvat-kvrocks-0 -n cvat -- sh -c 'du -sh /var/lib/kvrocks/db/*.sst' | tail -5

# Сбросить весь кэш
kubectl exec -i cvat-kvrocks-0 -n cvat -- \
  redis-cli -a cvat_kvrocks -p 6666 FLUSHDB
# OK

# ВАЖНО: FLUSHDB только маркирует записи tombstones!
# RocksDB не освобождает место до compaction.
# Нужно принудительно запустить compaction:
kubectl exec -i cvat-kvrocks-0 -n cvat -- \
  redis-cli -a cvat_kvrocks -p 6666 COMPACT
# OK (compaction занимает 30-60 секунд)

# Проверить результат (подождать ~30 сек)
sleep 30
kubectl exec -i cvat-kvrocks-0 -n cvat -- df -h /var/lib/kvrocks/db
```

```
┌─────────────────────────────────────────────────────────────────┐
│        KVRocks Cache — Как это работает                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   CVAT cache "media":                                            │
│     backend = django.core.cache.backends.redis.RedisCache        │
│     location = redis://:cvat_kvrocks@cvat-kvrocks:6666          │
│     timeout = 86400 (24 часа TTL)                                │
│                                                                  │
│   Что кэшируется:                                                │
│   - Декодированные image chunks (группы кадров)                  │
│   - Размер chunk зависит от image_quality:                       │
│     • quality=70  → ~50-100MB на chunk (сжатие JPEG)            │
│     • quality=100 → ~200-300MB на chunk (без сжатия)            │
│                                                                  │
│   Проблема:                                                      │
│   - Auto-annotation кэширует ВСЕ кадры задачи                   │
│   - Задача 3930 imgs × quality=100 ≈ 40-50GB кэша              │
│   - TTL 24ч → старые записи не вытесняются быстро              │
│                                                                  │
│   RocksDB storage:                                               │
│   WAL → компактируется → SST файлы (~256MB каждый)              │
│   archive/ → отработанные WAL (безопасно удалять)               │
│                                                                  │
│   Освобождение места:                                            │
│   1. rm archive/* → освобождает WAL                              │
│   2. FLUSHDB → маркирует tombstones (место НЕ освобождается!)   │
│   3. COMPACT → перезаписывает SST, удаляя tombstones            │
│                                                                  │
│   Пример: 344 SST × 128MB = 44GB → FLUSHDB+COMPACT → 161MB    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Примечание:** При `kubectl exec` в kvrocks pod использовать `-i` без `-t`, иначе возможен panic kubectl из-за бага terminalSizeQueueAdapter в старых версиях.

---

**Инцидент 2026-01-29:** PVC 20Gi заполнен на 97% (19GB из 20GB). Архив WAL занимал 5.8GB. После очистки архива — 65% (13GB из 20GB). PVC расширен до 30Gi.

**Инцидент 2026-02-10:** PVC 35Gi заполнен на 100% (35G/35G). Симптом: CVAT 500 "Could not receive image data". В логах backend: `redis.exceptions.ResponseError: IO error: No space left on device: While appending to file: /var/lib/kvrocks/db/005718.log`. Архив WAL занимал 2.9G. Очистка архива дала 92% (32G/35G). Расширение до 50Gi блокировалось Longhorn admission webhook — на нодах polynode-2 и polynode-3 не хватало headroom для 50Gi реплики (headroom ~4.5Gi и ~39.5Gi). Решение: уменьшить numberOfReplicas до 1 (только polydev-desktop с headroom 1348Gi), вручную удалить реплики с worker нод, расширить PVC до 50Gi, рестарт pod. Результат: 50Gi, 32G используется (65%), 1 реплика. Вторая реплика не создана — ни одна worker нода не имеет 50Gi headroom.

**Инцидент 2026-02-11:** PVC 50Gi заполнен на 100% (49G/50G) менее чем за сутки после расширения. Причина: auto-annotation (inference) на задаче #19 (3930 imgs, `image_quality=100`) закэшировал все кадры — 344 SST файла по ~128MB. Симптом: в Browser Console — `Inference status for task 19 is failed`, traceback до `redis.exceptions.ResponseError: IO error: No space left on device`. Решение: `FLUSHDB` + `COMPACT` → 161MB / 50GB (1%). Вывод: `image_quality=100` + inference на крупных задачах = быстрое заполнение KVRocks. Рекомендация: использовать `image_quality=70` для задач с auto-annotation.

### DiskPressure на GPU ноде

**Симптом:** Pod evicted, статус Error, в events:
```
The node was low on resource: ephemeral-storage
```

**Причина:** PyTorch CUDA образы очень большие (~8-12GB). При скачивании нескольких образов диск переполняется.

**Диагностика:**
```bash
# Проверить состояние ноды
kubectl describe node polydev-desktop | grep -A5 "Conditions:"

# Проверить свободное место (на ноде)
df -h /var/lib/containerd
```

**Решение:**
```bash
# На GPU ноде (polydev-desktop):

# Удалить неиспользуемые образы containerd
sudo crictl rmi --prune

# Или через k3s
sudo k3s crictl rmi --prune

# Проверить что DiskPressure снялся
kubectl describe node polydev-desktop | grep DiskPressure
```

**Профилактика:**
- Использовать меньшие базовые образы (runtime вместо devel)
- Добавить отдельный диск для containerd
- Настроить image garbage collection в kubelet

### Полезные ссылки

- [Nuclio Documentation](https://nuclio.io/docs/latest/)
- [CVAT Serverless Tutorial](https://docs.cvat.ai/docs/administration/advanced/installation_automatic_annotation/)
- [CVAT Serverless Functions](https://github.com/cvat-ai/cvat/tree/develop/serverless)

---

## См. также

- [[K3s]]
- [[K3s - Архитектура]] — схема взаимодействия сервисов
- [[Kubernetes - Сеть и взаимодействие]] — теория networking
- [[Services]] — типы сервисов, порты
- [[MetalLB]]
- [[MinIO]] — S3 storage для данных
- [[ClearML]] — MLOps платформа
- [[Longhorn]]
- [[Helm]]
- [[polydev-desktop]] — GPU нода для Nuclio функций
- [[K3s - Troubleshooting]]
- [CVAT Documentation](https://docs.cvat.ai/)
- [CVAT GitHub](https://github.com/cvat-ai/cvat)

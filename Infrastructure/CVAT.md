---
tags:
  - kubernetes
  - ml
  - annotation
  - infrastructure
created: 2026-01-19
updated: 2026-01-20
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
      size: 20Gi

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
| `cvat-kvrocks-data` | KVRocks storage | 20Gi |
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

#### GPU не используется

```bash
# Проверить что GPU нода видна
kubectl get nodes -l nvidia.com/gpu=true

# Проверить RuntimeClass
kubectl get runtimeclass nvidia

# Проверить что функция запросила GPU
kubectl describe pod -n cvat -l nuclio.io/function-name=<func-name> | grep nvidia
```

#### DiskPressure на GPU ноде

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
- [[MetalLB]]
- [[MinIO]] — S3 storage для данных
- [[Longhorn]]
- [[Helm]]
- [[polydev-desktop]] — GPU нода для Nuclio функций
- [[K3s - Troubleshooting]]
- [CVAT Documentation](https://docs.cvat.ai/)
- [CVAT GitHub](https://github.com/cvat-ai/cvat)

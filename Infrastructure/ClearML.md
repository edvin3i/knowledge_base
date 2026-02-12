---
tags:
  - kubernetes
  - mlops
  - infrastructure
created: 2026-01-20
updated: 2026-02-12
---

# ClearML

MLOps платформа в [[K3s]] кластере. Управление экспериментами, оркестрация задач, версионирование данных.

## Теория: Что такое ClearML

### Назначение

**ClearML** — open-source MLOps платформа:
- Трекинг экспериментов (metrics, hyperparameters, artifacts)
- Оркестрация ML пайплайнов
- Управление датасетами
- Запуск задач на удалённых агентах (в т.ч. с GPU)

### Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                    ClearML в кластере                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│   │   Python    │     │   Agent     │     │   Agent     │       │
│   │   SDK       │     │   (CPU)     │     │   (GPU)     │       │
│   └──────┬──────┘     └──────┬──────┘     └──────┬──────┘       │
│          │                   │                   │               │
│          └───────────────────┼───────────────────┘               │
│                              │ API                               │
│                              ▼                                   │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │                    ClearML Server                         │  │
│   │  ┌────────────┐  ┌────────────┐  ┌────────────┐         │  │
│   │  │ Web Server │  │ API Server │  │File Server │         │  │
│   │  │   :80      │  │   :80      │  │   :80      │         │  │
│   │  └────────────┘  └────────────┘  └────────────┘         │  │
│   └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│          ┌───────────────────┼───────────────────┐              │
│          ▼                   ▼                   ▼              │
│   ┌────────────┐      ┌────────────┐      ┌────────────┐       │
│   │  MongoDB   │      │   Redis    │      │Elasticsearch│       │
│   │   10Gi     │      │    5Gi     │      │    10Gi    │       │
│   └────────────┘      └────────────┘      └────────────┘       │
│                                                                  │
│   Артефакты (модели, датасеты) → [[MinIO]]                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Компоненты:**

| Компонент | Назначение |
|-----------|------------|
| **webserver** | Web UI для просмотра экспериментов |
| **apiserver** | REST API для SDK и агентов |
| **fileserver** | Хранение debug samples, plots (10Gi) |
| **MongoDB** | Метаданные экспериментов |
| **Elasticsearch** | Поиск и индексация |
| **Redis** | Очереди задач |

---

## Статус

| Параметр | Значение |
|----------|----------|
| **Версия** | 2.0.0 (chart 7.14.7) |
| **Namespace** | `clearml` |
| **Storage** | [[Longhorn]] (~35Gi total) |
| **Artifacts** | [[MinIO]] (buckets: `clearml`, `datasets`, `models`) |
| **Agent** | K8s Glue Agent v2.0.7, кастомный образ |
| **Agent Chart** | clearml-agent 5.3.3 |

---

## Доступ

| Сервис | URL | Назначение |
|--------|-----|------------|
| **Web UI** | http://192.168.20.240 | Интерфейс управления |
| **API Server** | http://192.168.20.242 | SDK/Agents подключение |
| **File Server** | http://192.168.20.241 | Загрузка файлов |

---

## Установка

### Helm chart

```bash
# Добавить репозиторий
helm repo add clearml https://allegroai.github.io/clearml-helm-charts
helm repo update

# Создать values
cat > clearml-values.yaml << 'EOF'
# Web Server - UI
webserver:
  service:
    type: LoadBalancer
    port: 80

# API Server - SDK/agents
apiserver:
  service:
    type: LoadBalancer
    port: 80

# File Server - для UI uploads
fileserver:
  service:
    type: LoadBalancer
    port: 80
  storage:
    enabled: true
    data:
      class: longhorn
      size: 10Gi

# Redis
redis:
  enabled: true
  architecture: standalone
  auth:
    enabled: false
  master:
    persistence:
      storageClass: longhorn
      size: 5Gi

# MongoDB
mongodb:
  enabled: true
  architecture: standalone
  auth:
    enabled: false
  persistence:
    storageClass: longhorn
    size: 10Gi

# Elasticsearch
elasticsearch:
  enabled: true
  replicas: 1
  esJavaOpts: "-Xmx2g -Xms2g"
  volumeClaimTemplate:
    storageClassName: longhorn
    resources:
      requests:
        storage: 10Gi
EOF

# Установить
helm install clearml clearml/clearml \
  --namespace clearml \
  --create-namespace \
  -f clearml-values.yaml
```

### Исправление targetPort (если нужно)

После установки сервисы могут иметь неправильный targetPort. Исправление:

```bash
kubectl patch svc clearml-apiserver -n clearml --type=json \
  -p='[{"op":"replace","path":"/spec/ports/0/targetPort","value":8008}]'

kubectl patch svc clearml-fileserver -n clearml --type=json \
  -p='[{"op":"replace","path":"/spec/ports/0/targetPort","value":8081}]'

# webserver использует nginx на порту 80, targetPort должен быть 80
kubectl patch svc clearml-webserver -n clearml --type=json \
  -p='[{"op":"replace","path":"/spec/ports/0/targetPort","value":80}]'
```

### Проверка

```bash
kubectl get pods -n clearml
kubectl get svc -n clearml
kubectl get pvc -n clearml
```

---

## Настройка SDK

### Установка

```bash
pip install clearml
```

### Конфигурация

Создать `~/clearml.conf`:

```hocon
api {
    web_server: http://192.168.20.240
    api_server: http://192.168.20.242
    files_server: http://192.168.20.241

    # Credentials (из Web UI → Settings → Workspace → Create new credentials)
    credentials {
        "access_key" = "YOUR_ACCESS_KEY"
        "secret_key" = "YOUR_SECRET_KEY"
    }
}

# MinIO для артефактов
sdk {
    aws {
        s3 {
            credentials: [{
                # Порт 80, т.к. MinIO за LoadBalancer (MetalLB), а не напрямую на :9000
                host: "192.168.20.237:80"
                key: "fsadm"
                secret: "minimiAdmin"
                multipart: false
                secure: false
            }]
        }
    }

    # Артефакты по умолчанию сохранять в MinIO
    development {
        default_output_uri: "s3://192.168.20.237:80/clearml"
    }
}
```

Или через wizard:

```bash
clearml-init
```

---

## Использование

### Python SDK

```python
from clearml import Task

# Создать эксперимент
task = Task.init(
    project_name="My Project",
    task_name="Training Run"
)

# Логировать параметры (set_parameters — базовый способ)
task.set_parameters({"learning_rate": 0.001, "epochs": 100})
# Рекомендуется: task.connect() — авто-логирует изменения и позволяет override из UI
# params = {"learning_rate": 0.001, "epochs": 100}
# task.connect(params)

# Логировать метрики
logger = task.get_logger()
for epoch in range(100):
    logger.report_scalar("loss", "train", iteration=epoch, value=loss)

# Сохранить артефакт (в MinIO)
task.upload_artifact("model", artifact_object=model)
```

### Запуск обучения на GPU (execute_remotely)

Самый простой способ — добавить одну строку к обычному скрипту:

```python
from clearml import Task

task = Task.init(
    project_name="My Project",
    task_name="YOLOv7 Training"
)

# Эта строка отправляет задачу в очередь и завершает локальный процесс.
# Agent подхватит задачу, создаст pod с GPU, клонирует репо и запустит скрипт.
task.execute_remotely(queue_name="default")

# --- Всё ниже выполняется уже на Agent'е ---
import torch
model = ...
for epoch in range(100):
    loss = train(model)
    task.get_logger().report_scalar("loss", "train", iteration=epoch, value=loss)
```

**Как это работает:**
1. `Task.init()` создаёт эксперимент в ClearML Server, записывает git diff, requirements, параметры
2. `execute_remotely()` ставит задачу в очередь `default` и **останавливает** локальный скрипт
3. K8s Glue Agent видит задачу в очереди, создаёт training pod с GPU
4. Training pod клонирует репозиторий, устанавливает зависимости, запускает скрипт **с нуля**
5. Всё после `execute_remotely()` выполняется на GPU ноде в кластере

### Альтернатива: clearml-task CLI

Запуск без модификации кода — ClearML сам клонирует репо:

```bash
clearml-task --project "My Project" --name "Training" \
  --repo https://github.com/user/repo.git \
  --branch main \
  --script train.py \
  --queue default
```

---

## ClearML Agent (K8s Glue)

### Теория: Что такое K8s Glue Agent

ClearML Agent — это процесс, который **слушает очередь задач** и запускает их.
Есть два варианта развёртывания:

| Вариант | Как работает | Плюсы | Минусы |
|---------|-------------|-------|--------|
| **Bare Metal** | `clearml-agent daemon` на машине с GPU | Просто настроить | Ручное управление, нет изоляции |
| **K8s Glue** | Лёгкий pod-контроллер в кластере | Автоскейлинг, изоляция, K8s-native | Сложнее настроить |

**K8s Glue Agent** — это лёгкий контроллер (не требует GPU сам по себе), который:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Как работает K8s Glue Agent                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐    ┌──────────────────┐    ┌────────────────────┐     │
│  │  Ваш скрипт  │    │  ClearML Server  │    │  K8s Glue Agent   │     │
│  │  (ноутбук)   │    │  (API + Queue)   │    │  (pod контроллер) │     │
│  └──────┬───────┘    └────────┬─────────┘    └─────────┬──────────┘     │
│         │                     │                        │                │
│    1. task.init()             │                        │                │
│    execute_remotely() ───────►│ Задача в очереди       │                │
│         │                     │ "default"              │                │
│         │                     │◄──── 2. Polling ───────┤                │
│         │                     │      (каждые 5 сек)    │                │
│         │                     │                        │                │
│         │                     │── 3. Есть задача! ────►│                │
│         │                     │                        │                │
│         │                     │                ┌───────▼────────┐       │
│         │                     │                │ 4. kubectl     │       │
│         │                     │                │ create pod     │       │
│         │                     │                │ (GPU + CUDA)   │       │
│         │                     │                └───────┬────────┘       │
│         │                     │                        │                │
│         │                     │        ┌───────────────▼──────────┐     │
│         │                     │        │  Training Pod            │     │
│         │                     │        │  nvidia/cuda:12.1.0      │     │
│         │                     │        │  ┌────────────────────┐  │     │
│         │                     │◄───────│  │ git clone repo     │  │     │
│         │                     │metrics │  │ pip install -r ...  │  │     │
│         │                     │artifacts│ │ python train.py    │  │     │
│         │                     │        │  └────────────────────┘  │     │
│         │                     │        │  GPU: nvidia.com/gpu: 1  │     │
│         │                     │        └──────────────────────────┘     │
│         │                     │                                         │
│   5. Результаты в Web UI      │        6. Pod удаляется после          │
│      (metrics, model)         │           завершения задачи            │
│                               │                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Ключевые компоненты:**

| Компонент | Что это | Где работает |
|-----------|---------|-------------|
| **Glue Agent pod** | Контроллер (Python + kubectl) | Любая нода, без GPU |
| **Training pod** | Временный pod для обучения | polydev-desktop (GPU нода) |
| **k8s_glue_example.py** | Скрипт из clearml-agent, точка входа glue | Внутри agent pod |
| **basePodTemplate** | Шаблон training pod (GPU, nodeSelector) | В Helm values |

### Архитектура: Почему кастомный образ

Официальный Helm chart `clearml-agent` (v5.3.3) использует базовый образ `allegroai/clearml-agent-k8s-base:1.24-21`, который **содержит Python 3.6**. Это несовместимо с текущей версией `clearml-agent` (2.0.7+), которая требует Python 3.8+.

**Ошибка:** при попытке запуска agent падает с `re.error: bad inline flags` — Python 3.6 не поддерживает inline regex flags, используемые в новом коде.

Решение — **собрать кастомный Docker-образ** на основе Python 3.10:

```
clearml-k8s-agent:1.1 (кастомный, ~311MB)
├── python:3.10-slim (базовый образ)
├── kubectl (управление K8s)
├── clearml-agent (pip, текущая версия)
├── k8s_glue_example.py (из clearml-agent examples)
├── entrypoint.sh (запуск glue)
└── .bashrc (требует Helm chart)
```

### Сборка кастомного образа

**Dockerfile** (`~/Expirements/TrainingModels/clearml-agent-image/Dockerfile`):

```dockerfile
FROM python:3.10-slim

# kubectl для управления K8s pods
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git && \
    curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
    install kubectl /usr/local/bin/ && rm kubectl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# ClearML Agent + K8s glue
RUN pip install --no-cache-dir clearml-agent

# k8s_glue_example.py — точка входа для K8s Glue Agent
RUN AGENT_DIR=$(python3 -c "import clearml_agent; import os; print(os.path.dirname(clearml_agent.__file__))") && \
    cp "${AGENT_DIR}/../examples/k8s_glue_example.py" /root/k8s_glue_example.py 2>/dev/null || \
    curl -fsSL -o /root/k8s_glue_example.py \
    "https://raw.githubusercontent.com/clearml/clearml-agent/master/examples/k8s_glue_example.py"

# entrypoint.sh — Helm chart ожидает этот файл
RUN printf '#!/bin/bash\npython3 -u /root/k8s_glue_example.py --queue "${K8S_GLUE_QUEUE}" ${K8S_GLUE_EXTRA_ARGS}\n' > /root/entrypoint.sh && \
    chmod +x /root/entrypoint.sh

# .bashrc — chart делает source /root/.bashrc
RUN touch /root/.bashrc

WORKDIR /root
```

**Сборка:**
```bash
cd ~/Expirements/TrainingModels/clearml-agent-image
docker build -t clearml-k8s-agent:1.1 .
```

### Доставка образа в K3s (без registry)

> **Важно:** K3s использует **свой экземпляр containerd** с отдельным хранилищем образов.
> Образ нужно доставить на **каждую ноду**, где pod может быть запланирован.
> В нашем случае agent pod работает на polydev-desktop.

Типичная ошибка: импортировать образ на **управляющей машине** (emachine), а не на **ноде кластера** (polydev-desktop). K8s kubelet на polydev-desktop не видит образы из containerd на emachine.

```bash
# 1. Сохранить образ в tar
docker save clearml-k8s-agent:1.1 -o /tmp/clearml-k8s-agent.tar

# 2. Скопировать на ноду кластера
scp /tmp/clearml-k8s-agent.tar ivan@192.168.20.16:/tmp/

# 3. Импортировать в K3s containerd (на polydev-desktop)
ssh ivan@192.168.20.16
sudo k3s ctr images import /tmp/clearml-k8s-agent.tar

# 4. Проверить
sudo k3s ctr images list | grep clearml
# docker.io/library/clearml-k8s-agent:1.1 ... 304.2 MiB
```

> **Про imagePullPolicy и теги:**
> - Тег `latest` → Kubernetes ставит `imagePullPolicy: Always` (всегда тянет из registry)
> - Любой другой тег (`1.0`, `v2`) → `imagePullPolicy: IfNotPresent` (сначала ищет локально)
> - Для локальных образов **без registry** всегда используйте конкретный тег, иначе pod получит `ErrImagePull`

### Helm values

**Файл:** `~/Expirements/TrainingModels/clearml-agent-values.yaml`

```yaml
# === Credentials (из WebUI → Settings → Workspace) ===
clearml:
  agentk8sglueKey: "YOUR_ACCESS_KEY"
  agentk8sglueSecret: "YOUR_SECRET_KEY"
  # MinIO для артефактов (модели, датасеты)
  clearmlConfig: |-
    sdk {
      aws {
        s3 {
          credentials: [{
            host: "192.168.20.237:80"
            key: "fsadm"
            secret: "minimiAdmin"
            multipart: false
            secure: false
            bucket: "clearml"
          },
          {
            host: "192.168.20.237:80"
            key: "fsadm"
            secret: "minimiAdmin"
            multipart: false
            secure: false
            bucket: "datasets"
          },
          {
            host: "192.168.20.237:80"
            key: "fsadm"
            secret: "minimiAdmin"
            multipart: false
            secure: false
            bucket: "models"
          }]
        }
      }
      development {
        default_output_uri: "s3://192.168.20.237:80/models"
      }
    }

# === Glue Agent — лёгкий контроллер, слушает очередь ===
agentk8sglue:
  # Кастомный образ (Python 3.10 + clearml-agent + kubectl)
  image:
    repository: "library/clearml-k8s-agent"
    tag: "1.1"

  # Подключение к ClearML Server (внутри кластера)
  apiServerUrlReference: "http://clearml-apiserver.clearml:80"
  fileServerUrlReference: "http://clearml-fileserver.clearml:80"
  webServerUrlReference: "http://192.168.20.240"
  clearmlcheckCertificate: false

  # Очередь для прослушивания
  queue: "default"
  createQueueIfNotExists: true

  # Docker-образ по умолчанию для задач обучения
  defaultContainerImage: "nvidia/cuda:12.1.0-runtime-ubuntu22.04"

  # === Шаблон pod'а для ЗАДАЧ ОБУЧЕНИЯ (спавнятся динамически) ===
  basePodTemplate:
    # GPU для каждой задачи
    resources:
      limits:
        nvidia.com/gpu: 1

    # Запускать на GPU ноде (polydev-desktop)
    nodeSelector:
      kubernetes.io/hostname: polydev-desktop

    # Переменные для NVIDIA runtime
    env:
      - name: NVIDIA_VISIBLE_DEVICES
        value: "all"
```

**Параметры values:**

| Параметр | Что делает |
|----------|-----------|
| `agentk8sglueKey/Secret` | API credentials из ClearML WebUI → Settings → Workspace |
| `clearmlConfig` | HOCON-конфиг с credentials для MinIO (S3-совместимый) |
| `apiServerUrlReference` | Внутрикластерный URL apiserver (Service DNS) |
| `webServerUrlReference` | Внешний URL WebUI (через [[MetalLB]] LoadBalancer) |
| `image.repository` | Без `docker.io/` — chart добавляет prefix сам |
| `image.tag` | Конкретный тег (не `latest`!) для локальных образов |
| `queue` | Имя очереди для прослушивания |
| `defaultContainerImage` | Базовый Docker-образ для training pod'ов |
| `basePodTemplate` | Шаблон K8s pod для training задач (GPU, nodeSelector) |

### Установка Agent

```bash
# Добавить репозиторий (если не добавлен)
helm repo add clearml https://allegroai.github.io/clearml-helm-charts
helm repo update

# Установить
helm install clearml-agent clearml/clearml-agent \
  --namespace clearml \
  -f ~/Expirements/TrainingModels/clearml-agent-values.yaml

# Проверить
kubectl get pods -n clearml | grep agent
# clearml-agent-xxx   1/1   Running   0   ...
```

### Обновление Agent

При изменении Dockerfile или values:

```bash
# 1. Пересобрать образ (увеличить тег!)
cd ~/Expirements/TrainingModels/clearml-agent-image
docker build -t clearml-k8s-agent:1.2 .

# 2. Доставить на ноду
docker save clearml-k8s-agent:1.2 -o /tmp/clearml-k8s-agent.tar
scp /tmp/clearml-k8s-agent.tar ivan@192.168.20.16:/tmp/
ssh ivan@192.168.20.16 "sudo k3s ctr images import /tmp/clearml-k8s-agent.tar"

# 3. Обновить tag в values.yaml: tag: "1.2"

# 4. Helm upgrade
helm upgrade clearml-agent clearml/clearml-agent \
  --namespace clearml \
  -f ~/Expirements/TrainingModels/clearml-agent-values.yaml

# 5. Проверить
kubectl get pods -n clearml | grep agent
kubectl logs -n clearml -l app.kubernetes.io/instance=clearml-agent --tail=20
```

### Проверка работы Agent

```bash
# Логи — должно быть "Listening to queues: default"
kubectl logs -n clearml -l app.kubernetes.io/instance=clearml-agent --tail=20

# Ожидаемый вывод:
# Worker "clearml-agent" - Listening to queues:
# | id                               | name    | tags |
# | 16fe1a40dcf7464cadaae61e002e58c0 | default |      |
# No tasks in Queues, sleeping for 5.0 seconds
```

---

## Storage

### Типы хранения

| Тип | Что хранит | Где |
|-----|------------|-----|
| **fileserver** | Debug samples, plots | Longhorn PVC (10Gi) |
| **MinIO** | Артефакты (модели, датасеты) | S3 bucket `clearml` |

### Создать bucket в MinIO

Через MinIO Console: http://192.168.20.238 → Buckets → Create Bucket → `clearml`

Или через CLI (если установлен MinIO Client):
```bash
mc alias set homelab http://192.168.20.237 fsadm minimiAdmin
mc mb homelab/clearml
```

---

## Troubleshooting

### Agent: ErrImagePull / ImagePullBackOff

**Симптом:** Agent pod stuck в `Init:ErrImagePull`, логи показывают `pull access denied`

**Возможные причины и решения:**

**1. Образ не на той машине**

Самая частая ошибка. Образ импортирован в containerd на **управляющей машине** (emachine), а pod запланирован на **ноде кластера** (polydev-desktop).

```bash
# Проверить на какой ноде pod
kubectl get pods -n clearml -o wide | grep agent

# Образ нужен на ТОЙ ноде. Импортировать:
docker save clearml-k8s-agent:1.1 -o /tmp/clearml-k8s-agent.tar
scp /tmp/clearml-k8s-agent.tar ivan@192.168.20.16:/tmp/
ssh ivan@192.168.20.16 "sudo k3s ctr images import /tmp/clearml-k8s-agent.tar"
```

**2. Тег `latest` → Always Pull**

Kubernetes для тега `latest` автоматически ставит `imagePullPolicy: Always`, что заставляет kubelet тянуть из registry даже если образ есть локально.

```bash
# Решение: использовать конкретный тег
docker tag clearml-k8s-agent:latest clearml-k8s-agent:1.1
# И в values.yaml: tag: "1.1"
```

**3. Двойной prefix docker.io**

Chart добавляет `docker.io/` к `repository`. Если в values написать `docker.io/library/clearml-k8s-agent`, итоговый путь будет `docker.io/docker.io/library/...`.

```yaml
# НЕПРАВИЛЬНО:
image:
  repository: "docker.io/library/clearml-k8s-agent"

# ПРАВИЛЬНО:
image:
  repository: "library/clearml-k8s-agent"
```

**4. Неправильный containerd socket (не K3s)**

Если на хосте есть и Docker, и K3s, команда `ctr` подключается к containerd Docker'а, а не K3s.

```bash
# Docker containerd (НЕПРАВИЛЬНЫЙ для K3s):
sudo ctr -n k8s.io images import image.tar

# K3s containerd (ПРАВИЛЬНЫЙ):
sudo k3s ctr images import image.tar
# или с явным socket:
sudo ctr --address /run/k3s/containerd/containerd.sock -n k8s.io images import image.tar
```

### Agent: CrashLoopBackOff (Python 3.6)

**Симптом:** Agent pod в CrashLoopBackOff, логи показывают `re.error: bad inline flags`

**Причина:** Официальный базовый образ `allegroai/clearml-agent-k8s-base:1.24-21` содержит Python 3.6, несовместимый с clearml-agent 2.0+.

**Решение:** Собрать кастомный образ на Python 3.10 (см. раздел "Сборка кастомного образа").

### Agent: entrypoint.sh not found

**Симптом:** Agent pod в CrashLoopBackOff, Exit Code 127, `/root/entrypoint.sh: No such file or directory`

**Причина:** Кастомный образ не содержит `entrypoint.sh`, который ожидает Helm chart.

**Решение:** Добавить в Dockerfile:
```dockerfile
RUN printf '#!/bin/bash\npython3 -u /root/k8s_glue_example.py --queue "${K8S_GLUE_QUEUE}" ${K8S_GLUE_EXTRA_ARGS}\n' > /root/entrypoint.sh && \
    chmod +x /root/entrypoint.sh
RUN touch /root/.bashrc
```

### Agent: Init:0/1 (waiting for apiserver)

**Симптом:** Init container зацикливается на `waiting for apiserver`

**Причина:** Неправильный URL или порт apiserver. Init container шлёт `curl` на указанный URL.

**Решение:**
```bash
# Проверить что apiserver отвечает изнутри кластера
kubectl exec -n clearml <any-pod> -- curl -s http://clearml-apiserver.clearml:80/debug.ping
# Должен вернуть 200

# В values:
apiServerUrlReference: "http://clearml-apiserver.clearml:80"  # Service DNS + port 80
```

### Pods не запускаются

**Симптом:** webserver/fileserver stuck в Init:0/1

**Причина:** Ждут apiserver, но targetPort неправильный

**Решение:**
```bash
# Проверить на каком порту слушает контейнер
kubectl exec -n clearml <pod> -- ss -tlnp

# Исправить targetPort сервиса
kubectl patch svc clearml-apiserver -n clearml --type=json \
  -p='[{"op":"replace","path":"/spec/ports/0/targetPort","value":8008}]'
```

### Elasticsearch не стартует

**Проверить:**
```bash
kubectl logs -n clearml clearml-elastic-master-0
```

**Частая причина:** Недостаточно памяти. Elasticsearch требует минимум 2Gi.

### SDK не подключается

**Проверить credentials:**
```bash
curl http://192.168.20.242/debug.ping
```

**Проверить конфиг:**
```bash
cat ~/clearml.conf
```

### Longhorn nodes Unschedulable (overallocation)

**Симптом:** После установки ClearML ноды Longhorn показывают красный Allocated и статус Unschedulable.

**Причина:** Сумма реплик volumes превышает доступное место на ноде.

**Диагностика:**
```bash
kubectl get nodes.longhorn.io -n longhorn-system
# Или через UI: http://192.168.20.239 → Nodes
```

**Решение:** Уменьшить размер PVC (требует переустановки):
```bash
helm uninstall clearml -n clearml
kubectl delete pvc --all -n clearml
# Отредактировать values с меньшими размерами
helm install clearml clearml/clearml -n clearml -f clearml-values.yaml
```

---

## Полезные команды

```bash
# Статус подов
kubectl get pods -n clearml

# Логи apiserver
kubectl logs -n clearml -l app.kubernetes.io/instance=clearml-apiserver

# Перезапустить webserver
kubectl rollout restart deployment clearml-webserver -n clearml

# PVC использование
kubectl get pvc -n clearml
```

---

## Инциденты

### 2026-02-12: Установка K8s Glue Agent

**Задача:** Установить ClearML Agent в K3s для запуска GPU-задач обучения.

**Проблемы и решения (хронология):**

| # | Проблема | Причина | Решение |
|---|----------|---------|---------|
| 1 | Init:0/1 — waiting for apiserver | URL в values указывал порт 8008, а K8s Service слушает на 80 | Исправить `apiServerUrlReference` на порт `:80` |
| 2 | CrashLoopBackOff — `re.error: bad inline flags` | Базовый образ `allegroai` содержит Python 3.6 | Собрать кастомный образ с Python 3.10 |
| 3 | CrashLoopBackOff — `/root/clearml.conf: Read-only file system` | Базовый образ монтирует conf как read-only | Решено кастомным образом |
| 4 | ErrImagePull — образ не найден | Образ импортирован на emachine (управляющая), а не на polydev-desktop (нода кластера) | `scp` + `sudo k3s ctr images import` на polydev-desktop |
| 5 | ErrImagePull — `pull access denied` (тег `latest`) | Для `latest` K8s ставит `imagePullPolicy: Always` | Использовать конкретный тег `1.1` |
| 6 | CrashLoopBackOff — `entrypoint.sh: No such file or directory` | Кастомный образ не содержал entrypoint.sh | Добавить entrypoint.sh и .bashrc в Dockerfile |

**Результат:** Agent pod `1/1 Running`, слушает очередь `default`.

---

## См. также

- [[K3s]]
- [[K3s - Архитектура]] — схема взаимодействия сервисов
- [[Kubernetes - Сеть и взаимодействие]] — теория networking
- [[Services]] — типы сервисов, порты
- [[Longhorn]]
- [[MinIO]]
- [[CVAT]]
- [[MetalLB]]
- [ClearML Documentation](https://clear.ml/docs/latest/)
- [ClearML Helm Charts](https://github.com/allegroai/clearml-helm-charts)

---
tags:
  - kubernetes
  - mlops
  - infrastructure
created: 2026-01-20
updated: 2026-01-20
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
| **Artifacts** | [[MinIO]] (bucket: `clearml`) |

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

# Логировать параметры
task.set_parameters({"learning_rate": 0.001, "epochs": 100})

# Логировать метрики
logger = task.get_logger()
for epoch in range(100):
    logger.report_scalar("loss", "train", iteration=epoch, value=loss)

# Сохранить артефакт (в MinIO)
task.upload_artifact("model", artifact_object=model)
```

### ClearML Agent

Для запуска задач на удалённых машинах (включая GPU):

```bash
# На машине с GPU
pip install clearml-agent

# Настроить
clearml-agent init

# Запустить агент
clearml-agent daemon --queue default --gpus 0
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

## См. также

- [[K3s]]
- [[Longhorn]]
- [[MinIO]]
- [[MetalLB]]
- [ClearML Documentation](https://clear.ml/docs/latest/)
- [ClearML Helm Charts](https://github.com/allegroai/clearml-helm-charts)

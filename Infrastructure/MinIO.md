---
tags:
  - kubernetes
  - storage
  - infrastructure
  - s3
created: 2026-01-20
---

# MinIO

S3-совместимое объектное хранилище в [[K3s]] кластере.

## Теория: Что такое MinIO

### Назначение

**MinIO** — высокопроизводительное объектное хранилище с S3-совместимым API:
- Хранение файлов, артефактов, датасетов
- Совместимость с AWS S3 SDK
- Self-hosted альтернатива AWS S3

### Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    MinIO в кластере                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌─────────┐     ┌─────────┐     ┌─────────────┐          │
│   │  CVAT   │     │ ClearML │     │ Другие apps │          │
│   └────┬────┘     └────┬────┘     └──────┬──────┘          │
│        │               │                  │                 │
│        └───────────────┼──────────────────┘                 │
│                        │ S3 API                             │
│                        ▼                                    │
│              ┌──────────────────┐                          │
│              │   MinIO Server   │                          │
│              │                  │                          │
│              │  Buckets:        │                          │
│              │  - cvat          │                          │
│              │  - clearml       │                          │
│              │  - datasets      │                          │
│              │  - models        │                          │
│              └────────┬─────────┘                          │
│                       │                                     │
│                       ▼                                     │
│              ┌──────────────────┐                          │
│              │  Longhorn PVC    │                          │
│              │     100Gi        │                          │
│              └──────────────────┘                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Статус

| Параметр | Значение |
|----------|----------|
| **Namespace** | `minio` |
| **Mode** | Standalone |
| **Storage** | 100Gi ([[Longhorn]]) |
| **API IP** | 192.168.20.237 |
| **Console IP** | 192.168.20.238 |

---

## Доступ

| Сервис | URL | Назначение |
|--------|-----|------------|
| **MinIO API** | http://192.168.20.237 | S3 API для приложений |
| **MinIO Console** | http://192.168.20.238 | Web UI управления |

**Credentials:**
- **User:** `fsadm`
- **Password:** `minimiAdmin`

---

## Установка

### Helm chart

```bash
# Добавить репозиторий
helm repo add minio https://charts.min.io/
helm repo update

# Создать values
cat > minio-values.yaml << 'EOF'
mode: standalone
replicas: 1

persistence:
  enabled: true
  size: 100Gi
  storageClass: longhorn

resources:
  requests:
    memory: 1Gi
    cpu: 250m
  limits:
    memory: 2Gi
    cpu: 1

rootUser: fsadm
rootPassword: minimiAdmin

service:
  type: LoadBalancer

buckets:
  - name: cvat
    policy: none
  - name: clearml
    policy: none
  - name: datasets
    policy: none
  - name: models
    policy: none
EOF

# Установить
helm install minio minio/minio \
  --namespace minio \
  --create-namespace \
  -f minio-values.yaml
```

### Настройка сервисов на порт 80

```bash
# API на порт 80
kubectl patch svc minio -n minio --type=json -p='[{"op":"replace","path":"/spec/ports/0/port","value":80}]'

# Console: удалить и создать заново
kubectl delete svc minio-console -n minio
kubectl create service loadbalancer minio-console --tcp=80:9001 -n minio
kubectl patch svc minio-console -n minio -p '{"spec":{"selector":{"app":"minio","release":"minio"}}}'
```

### Проверка

```bash
kubectl get pods -n minio
kubectl get svc -n minio
```

---

## Использование

### MinIO Client (mc)

```bash
# Установить mc
curl -O https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc
sudo mv mc /usr/local/bin/

# Настроить alias
mc alias set homelab http://192.168.20.237 fsadm minimiAdmin

# Операции
mc ls homelab                    # Список buckets
mc mb homelab/new-bucket         # Создать bucket
mc cp file.txt homelab/bucket/   # Загрузить файл
mc ls homelab/bucket/            # Содержимое bucket
```

### Python (boto3)

```python
import boto3

s3 = boto3.client(
    's3',
    endpoint_url='http://192.168.20.237',
    aws_access_key_id='fsadm',
    aws_secret_access_key='minimiAdmin'
)

# Список buckets
buckets = s3.list_buckets()
for b in buckets['Buckets']:
    print(b['Name'])

# Загрузить файл
s3.upload_file('local.txt', 'cvat', 'remote.txt')

# Скачать файл
s3.download_file('cvat', 'remote.txt', 'downloaded.txt')
```

### Kubernetes Secret для приложений

```bash
kubectl create secret generic minio-credentials \
  --from-literal=accesskey=fsadm \
  --from-literal=secretkey=minimiAdmin \
  -n <namespace>
```

---

## Buckets

| Bucket | Назначение |
|--------|------------|
| `cvat` | Данные [[CVAT]] (изображения, видео) |
| `clearml` | Артефакты [[ClearML]] (модели, датасеты) |
| `datasets` | ML датасеты |
| `models` | Обученные модели |

Создать bucket через Console или mc:

```bash
mc mb homelab/my-new-bucket
```

---

## Интеграция с приложениями

### CVAT

В CVAT можно подключить MinIO как Cloud Storage для импорта/экспорта данных.

1. Открыть CVAT → Cloud Storages
2. Добавить:
   - **Provider:** AWS S3
   - **Bucket:** cvat
   - **Access Key:** fsadm
   - **Secret Key:** minimiAdmin
   - **Endpoint URL:** http://192.168.20.237
   - **Region:** us-east-1 (любой)

### ClearML

В `~/clearml.conf`:

```hocon
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

---

## Troubleshooting

### Нет доступа к Console

**Проверить сервис:**
```bash
kubectl get svc minio-console -n minio
```

**Проверить selector:**
```bash
kubectl get svc minio-console -n minio -o jsonpath='{.spec.selector}'
# Должен быть: {"app":"minio","release":"minio"}
```

### Bucket не создаётся

**Проверить credentials:**
```bash
mc alias set test http://192.168.20.237 fsadm minimiAdmin
mc admin info test
```

### PVC не создаётся

**Проверить Longhorn:**
```bash
kubectl get pvc -n minio
kubectl describe pvc -n minio
```

---

## Backup

### Экспорт данных

```bash
# Синхронизировать bucket на локальный диск
mc mirror homelab/cvat /backup/minio/cvat
```

### Репликация между MinIO

```bash
mc mirror homelab/cvat remote/cvat --watch
```

---

## См. также

- [[K3s]]
- [[Longhorn]]
- [[CVAT]]
- [[ClearML]]
- [[MetalLB]]
- [MinIO Documentation](https://min.io/docs/minio/linux/index.html)
- [MinIO Helm Chart](https://github.com/minio/minio/tree/master/helm/minio)

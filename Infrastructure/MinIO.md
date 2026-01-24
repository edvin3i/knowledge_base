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

### MinIO Client (mcli)

> **Примечание:** Стандартная команда `mc` конфликтует с Midnight Commander. Поэтому устанавливаем как `mcli`.

```bash
# Установить как mcli (чтобы не конфликтовать с Midnight Commander)
curl -O https://dl.min.io/client/mc/release/linux-amd64/mc
sudo chmod +x mc
sudo mv mc /usr/local/bin/mcli

# Настроить alias
mcli alias set homelab http://192.168.20.237 fsadm minimiAdmin

# Основные операции
mcli ls homelab                           # Список buckets
mcli ls homelab/datasets/                 # Содержимое bucket
mcli mb homelab/new-bucket                # Создать bucket
mcli cp file.txt homelab/bucket/          # Загрузить файл
mcli cp -r /local/dir homelab/bucket/     # Загрузить директорию
mcli rm homelab/bucket/file.txt           # Удалить файл
mcli rm -r --force homelab/bucket/dir/    # Удалить директорию

# Синхронизация
mcli mirror /local/path homelab/bucket/   # Односторонняя синхронизация
mcli mirror --watch /local homelab/bucket # Непрерывная синхронизация

# Информация
mcli admin info homelab                   # Статус сервера
mcli du homelab/bucket/                   # Размер данных
```

---

### AWS CLI

Универсальный способ, работает с любым S3-совместимым хранилищем.

```bash
# Установить
pip install awscli
# или
sudo apt install awscli

# Настроить профиль для MinIO
aws configure --profile minio
# AWS Access Key ID: fsadm
# AWS Secret Access Key: minimiAdmin
# Default region: us-east-1
# Default output format: json

# Добавить alias в ~/.bashrc для удобства
cat >> ~/.bashrc << 'EOF'

# MinIO shortcuts
export MINIO_ENDPOINT="http://192.168.20.237"
alias minio="aws --profile minio --endpoint-url \$MINIO_ENDPOINT s3"
alias minio-api="aws --profile minio --endpoint-url \$MINIO_ENDPOINT s3api"
EOF
source ~/.bashrc

# Основные операции
minio ls                                  # Список buckets
minio ls s3://datasets/                   # Содержимое bucket
minio mb s3://new-bucket                  # Создать bucket
minio cp file.txt s3://bucket/            # Загрузить файл
minio cp --recursive /dir s3://bucket/    # Загрузить директорию
minio sync /local/path s3://bucket/path/  # Синхронизация
minio rm s3://bucket/file.txt             # Удалить файл

# Без alias (полная команда)
aws --profile minio --endpoint-url http://192.168.20.237 s3 ls
```

### Python (boto3)

Для скриптов и автоматизации.

```bash
pip install boto3
```

```python
import boto3
from pathlib import Path

# Создать клиент
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
s3.upload_file('local.txt', 'datasets', 'path/remote.txt')

# Скачать файл
s3.download_file('datasets', 'path/remote.txt', 'downloaded.txt')

# Список объектов в bucket
response = s3.list_objects_v2(Bucket='datasets', Prefix='polyvision/')
for obj in response.get('Contents', []):
    print(obj['Key'], obj['Size'])

# Удалить объект
s3.delete_object(Bucket='datasets', Key='path/file.txt')
```

#### Загрузка директории рекурсивно

```python
from pathlib import Path
import boto3

def upload_directory(local_dir: str, bucket: str, prefix: str = ""):
    """Загрузить директорию в MinIO рекурсивно."""
    s3 = boto3.client(
        's3',
        endpoint_url='http://192.168.20.237',
        aws_access_key_id='fsadm',
        aws_secret_access_key='minimiAdmin'
    )

    local_path = Path(local_dir)
    uploaded = 0

    for file in local_path.rglob('*'):
        if file.is_file():
            key = f"{prefix}/{file.relative_to(local_path)}" if prefix else str(file.relative_to(local_path))
            s3.upload_file(str(file), bucket, key)
            uploaded += 1
            print(f"✓ {key}")

    print(f"\nUploaded {uploaded} files to s3://{bucket}/{prefix}")

# Пример: загрузить датасет
upload_directory(
    "/home/edvin/Expirements/Datasets/mixed_dataset_26500/Polyvision_dataset_five_classes_v1.1",
    "datasets",
    "polyvision_v1.1"
)
```

#### Скачивание директории

```python
import os
from pathlib import Path
import boto3

def download_directory(bucket: str, prefix: str, local_dir: str):
    """Скачать директорию из MinIO."""
    s3 = boto3.client(
        's3',
        endpoint_url='http://192.168.20.237',
        aws_access_key_id='fsadm',
        aws_secret_access_key='minimiAdmin'
    )

    local_path = Path(local_dir)
    paginator = s3.get_paginator('list_objects_v2')
    downloaded = 0

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get('Contents', []):
            key = obj['Key']
            rel_path = key[len(prefix):].lstrip('/')
            target = local_path / rel_path

            target.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(bucket, key, str(target))
            downloaded += 1
            print(f"✓ {rel_path}")

    print(f"\nDownloaded {downloaded} files to {local_dir}")

# Пример: скачать датасет
download_directory("datasets", "polyvision_v1.1/", "/tmp/polyvision")
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
- [[K3s - Архитектура]] — схема взаимодействия сервисов
- [[Kubernetes - Сеть и взаимодействие]] — теория networking
- [[Services]] — типы сервисов, порты
- [[Longhorn]]
- [[CVAT]]
- [[ClearML]]
- [[MetalLB]]
- [MinIO Documentation](https://min.io/docs/minio/linux/index.html)
- [MinIO Helm Chart](https://github.com/minio/minio/tree/master/helm/minio)

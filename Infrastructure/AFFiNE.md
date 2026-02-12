---
tags:
  - kubernetes
  - collaboration
  - infrastructure
created: 2026-01-27
---

# AFFiNE

Collaborative workspace (альтернатива Notion + Miro) в [[K3s]] кластере.

## Теория: Что такое AFFiNE

### Назначение

**AFFiNE** — open-source платформа для заметок, документов и визуального планирования:
- Документы и заметки (как Notion)
- Whiteboards (как Miro)
- Локальное хранение данных (privacy-first)
- Real-time collaboration

### Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                     AFFiNE Architecture                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│   Browser ───► LoadBalancer (192.168.20.243)                     │
│                      │                                            │
│                      ▼                                            │
│              ┌──────────────────┐                                │
│              │  AFFiNE Server   │  Port 3010                     │
│              │   (Node.js)      │                                │
│              └────────┬─────────┘                                │
│                       │                                           │
│         ┌─────────────┼─────────────┐                            │
│         ▼             ▼             ▼                            │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐                      │
│   │PostgreSQL│  │  Redis   │  │ Storage  │                      │
│   │ +pgvector│  │  Cache   │  │  (PVC)   │                      │
│   └──────────┘  └──────────┘  └──────────┘                      │
│                                                                   │
│   Migration Job: node ./scripts/self-host-predeploy.js          │
│   (выполняется перед стартом сервера)                           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Компоненты:**

| Компонент | Назначение |
|-----------|------------|
| **AFFiNE Server** | Node.js приложение (GraphQL API + WebSocket) |
| **PostgreSQL** | Основная БД (с расширением pgvector для AI) |
| **Redis** | Кэш и сессии |
| **Storage PVC** | Хранение uploaded files |
| **Migration Job** | Инициализация схемы БД |

---

## Статус

| Параметр | Значение |
|----------|----------|
| **Namespace** | `affine` |
| **Version** | stable (latest) |
| **IP** | 192.168.20.243 ([[MetalLB]]) |
| **Storage** | [[Longhorn]] |

---

## Доступ

| Сервис | URL |
|--------|-----|
| **AFFiNE UI** | http://192.168.20.243 |

---

## Установка

### Вариант 1: Kubernetes манифесты (рекомендуется)

#### 1. Подготовка файлов

```bash
mkdir -p ~/k8s-manifests/affine
cd ~/k8s-manifests/affine
```

#### 2. namespace.yaml

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: affine
```

#### 3. secrets.yaml

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: affine-secrets
  namespace: affine
type: Opaque
stringData:
  DB_USERNAME: affine
  DB_PASSWORD: "CHANGE_ME_STRONG_PASSWORD"    # Заменить!
  DB_DATABASE: affine
  REDIS_PASSWORD: "CHANGE_ME_REDIS_PASSWORD"  # Заменить!
```

#### 4. postgres.yaml

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-data
  namespace: affine
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: longhorn
  resources:
    requests:
      storage: 10Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: affine
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  strategy:
    type: Recreate  # Важно для StatefulSet-like поведения с PVC
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: pgvector/pgvector:pg16
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_USER
          valueFrom:
            secretKeyRef:
              name: affine-secrets
              key: DB_USERNAME
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: affine-secrets
              key: DB_PASSWORD
        - name: POSTGRES_DB
          valueFrom:
            secretKeyRef:
              name: affine-secrets
              key: DB_DATABASE
        - name: PGDATA
          value: /var/lib/postgresql/data/pgdata
        volumeMounts:
        - name: postgres-data
          mountPath: /var/lib/postgresql/data
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          exec:
            command: ["pg_isready", "-U", "affine", "-d", "affine"]
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
        readinessProbe:
          exec:
            command: ["pg_isready", "-U", "affine", "-d", "affine"]
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
      volumes:
      - name: postgres-data
        persistentVolumeClaim:
          claimName: postgres-data
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: affine
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
```

**Разбор:**

| Элемент | Объяснение |
|---------|------------|
| `pgvector/pgvector:pg16` | PostgreSQL 16 с расширением pgvector (для AI features) |
| `strategy: Recreate` | Гарантирует что старый pod удалён перед созданием нового (важно для PVC RWO) |
| `PGDATA` subpath | Избегает проблемы с lost+found в корне volume |

#### 5. redis.yaml

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: affine
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        command:
        - redis-server
        - --requirepass
        - $(REDIS_PASSWORD)
        env:
        - name: REDIS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: affine-secrets
              key: REDIS_PASSWORD
        resources:
          requests:
            memory: "64Mi"
            cpu: "50m"
          limits:
            memory: "256Mi"
            cpu: "200m"
        livenessProbe:
          exec:
            command: ["redis-cli", "ping"]
          initialDelaySeconds: 10
          periodSeconds: 5
        readinessProbe:
          exec:
            command: ["redis-cli", "ping"]
          initialDelaySeconds: 5
          periodSeconds: 3
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: affine
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
```

#### 6. affine-storage.yaml

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: affine-storage
  namespace: affine
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: longhorn
  resources:
    requests:
      storage: 20Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: affine-config
  namespace: affine
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: longhorn
  resources:
    requests:
      storage: 1Gi
```

#### 7. affine-migration.yaml

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: affine-migration
  namespace: affine
spec:
  ttlSecondsAfterFinished: 300  # Удалить Job через 5 минут после завершения
  template:
    spec:
      restartPolicy: OnFailure
      initContainers:
      - name: wait-for-postgres
        image: busybox:1.36
        command:
        - sh
        - -c
        - |
          echo "Waiting for PostgreSQL..."
          until nc -z postgres 5432; do
            echo "PostgreSQL not ready, sleeping 2s..."
            sleep 2
          done
          echo "PostgreSQL is ready!"
      - name: wait-for-redis
        image: busybox:1.36
        command:
        - sh
        - -c
        - |
          echo "Waiting for Redis..."
          until nc -z redis 6379; do
            echo "Redis not ready, sleeping 2s..."
            sleep 2
          done
          echo "Redis is ready!"
      containers:
      - name: migration
        image: ghcr.io/toeverything/affine:stable
        command: ["node", "./scripts/self-host-predeploy.js"]
        env:
        - name: NODE_OPTIONS
          value: "--import=./scripts/register.js"
        - name: DATABASE_URL
          value: "postgresql://$(DB_USERNAME):$(DB_PASSWORD)@postgres:5432/$(DB_DATABASE)"
        - name: DB_USERNAME
          valueFrom:
            secretKeyRef:
              name: affine-secrets
              key: DB_USERNAME
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: affine-secrets
              key: DB_PASSWORD
        - name: DB_DATABASE
          valueFrom:
            secretKeyRef:
              name: affine-secrets
              key: DB_DATABASE
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

**Разбор:**

| Элемент | Объяснение |
|---------|------------|
| `ttlSecondsAfterFinished` | Автоматическая очистка завершённых Jobs |
| `initContainers` | Ждут готовности зависимостей перед запуском миграции |
| `self-host-predeploy.js` | Скрипт инициализации схемы БД |

#### 8. affine.yaml

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: affine
  namespace: affine
spec:
  replicas: 1
  selector:
    matchLabels:
      app: affine
  strategy:
    type: Recreate  # Важно для PVC RWO
  template:
    metadata:
      labels:
        app: affine
    spec:
      initContainers:
      # Ждём завершения миграции (или что БД уже инициализирована)
      - name: wait-for-db
        image: busybox:1.36
        command:
        - sh
        - -c
        - |
          echo "Waiting for PostgreSQL..."
          until nc -z postgres 5432; do
            sleep 2
          done
          echo "PostgreSQL is ready!"
      containers:
      - name: affine
        image: ghcr.io/toeverything/affine:stable
        ports:
        - containerPort: 3010
          name: http
        - containerPort: 5555
          name: prisma
        env:
        - name: NODE_OPTIONS
          value: "--import=./scripts/register.js"
        - name: AFFINE_CONFIG_PATH
          value: "/root/.affine/config"
        - name: NODE_ENV
          value: "production"
        - name: AFFINE_SERVER_HOST
          value: "0.0.0.0"
        - name: AFFINE_SERVER_PORT
          value: "3010"
        # Database
        - name: DATABASE_URL
          value: "postgresql://$(DB_USERNAME):$(DB_PASSWORD)@postgres:5432/$(DB_DATABASE)"
        - name: DB_USERNAME
          valueFrom:
            secretKeyRef:
              name: affine-secrets
              key: DB_USERNAME
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: affine-secrets
              key: DB_PASSWORD
        - name: DB_DATABASE
          valueFrom:
            secretKeyRef:
              name: affine-secrets
              key: DB_DATABASE
        # Redis
        - name: REDIS_SERVER_HOST
          value: "redis"
        - name: REDIS_SERVER_PORT
          value: "6379"
        - name: REDIS_SERVER_PASSWORD
          valueFrom:
            secretKeyRef:
              name: affine-secrets
              key: REDIS_PASSWORD
        volumeMounts:
        - name: storage
          mountPath: /root/.affine/storage
        - name: config
          mountPath: /root/.affine/config
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /
            port: 3010
          initialDelaySeconds: 60
          periodSeconds: 30
          timeoutSeconds: 10
        readinessProbe:
          httpGet:
            path: /
            port: 3010
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
      volumes:
      - name: storage
        persistentVolumeClaim:
          claimName: affine-storage
      - name: config
        persistentVolumeClaim:
          claimName: affine-config
---
apiVersion: v1
kind: Service
metadata:
  name: affine
  namespace: affine
  annotations:
    metallb.universe.tf/address-pool: default-pool
spec:
  type: LoadBalancer
  loadBalancerIP: 192.168.20.243  # Свободный IP из пула MetalLB
  selector:
    app: affine
  ports:
  - name: http
    port: 80
    targetPort: 3010
```

**Разбор:**

| Элемент | Объяснение |
|---------|------------|
| `ghcr.io/toeverything/affine:stable` | Официальный образ AFFiNE |
| `loadBalancerIP` | Фиксированный IP от [[MetalLB]] |
| `port: 80, targetPort: 3010` | Внешний порт 80, внутренний 3010 |

**Важно о Docker образах:**

| Образ | Назначение |
|-------|------------|
| `ghcr.io/toeverything/affine:stable` | Рекомендуемый для self-host с PostgreSQL/Redis |
| `ghcr.io/toeverything/affine-self-hosted` | Упрощённый single-container вариант |
| `ghcr.io/toeverything/affine-graphql` | Legacy название (может не работать) |

**Выбор IP для LoadBalancer:**

Пул MetalLB: `192.168.20.235-249`. Занятые IP:

| IP | Сервис | Namespace |
|----|--------|-----------|
| 192.168.20.235 | Traefik (Ingress) | kube-system |
| 192.168.20.236 | Nuclio Dashboard | cvat |
| 192.168.20.237 | MinIO API | minio |
| 192.168.20.238 | MinIO Console | minio |
| 192.168.20.239 | Longhorn UI | longhorn-system |
| 192.168.20.240 | ClearML Web | clearml |
| 192.168.20.241 | ClearML Files | clearml |
| 192.168.20.242 | ClearML API | clearml |

Свободные: **192.168.20.243-249** — используем 243 для AFFiNE.

---

### Порядок деплоя

```bash
cd ~/k8s-manifests/affine

# 1. Создать namespace и secrets
kubectl apply -f namespace.yaml
kubectl apply -f secrets.yaml

# 2. Создать PVC (Longhorn автоматически создаст volumes)
kubectl apply -f affine-storage.yaml

# 3. Развернуть базы данных
kubectl apply -f postgres.yaml
kubectl apply -f redis.yaml

# 4. Дождаться готовности PostgreSQL
kubectl wait --namespace affine \
  --for=condition=ready pod \
  -l app=postgres \
  --timeout=180s

# 5. Дождаться готовности Redis
kubectl wait --namespace affine \
  --for=condition=ready pod \
  -l app=redis \
  --timeout=60s

# 6. Запустить миграцию БД
kubectl apply -f affine-migration.yaml

# 7. Дождаться завершения миграции
kubectl wait --namespace affine \
  --for=condition=complete \
  job/affine-migration \
  --timeout=300s

# 8. Развернуть AFFiNE
kubectl apply -f affine.yaml

# 9. Проверить статус
kubectl get pods -n affine
kubectl get svc -n affine
```

### Проверка

```bash
# Все поды должны быть Running
kubectl get pods -n affine
# NAME                        READY   STATUS    RESTARTS   AGE
# affine-xxx                  1/1     Running   0          1m
# postgres-xxx                1/1     Running   0          3m
# redis-xxx                   1/1     Running   0          3m

# Сервис должен получить IP от MetalLB
kubectl get svc affine -n affine
# NAME     TYPE           EXTERNAL-IP      PORT(S)
# affine   LoadBalancer   192.168.20.243   80:xxxxx/TCP

# Логи AFFiNE
kubectl logs -n affine -l app=affine --tail=50
```

Открыть в браузере: **http://192.168.20.243**

---

### Вариант 2: Неофициальный Helm Chart

```bash
# Добавить репозиторий
helm repo add affine-chart https://chandr-andr.github.io/affine-chart
helm repo update

# Установить
helm install affine affine-chart/affine \
  --namespace affine \
  --create-namespace \
  --set image.tag=stable \
  --set replicaCount=1 \
  --set service.type=LoadBalancer \
  --set postgresql.enabled=true \
  --set postgresql.auth.password=CHANGE_ME \
  --set redis.enabled=true \
  --set redis.auth.password=CHANGE_ME \
  --set persistence.enabled=true \
  --set persistence.storageClass=longhorn \
  --set persistence.size=20Gi
```

**Примечание:** Helm chart неофициальный и может быть устаревшим. Рекомендуется использовать Kubernetes манифесты.

---

## Обновление

### Проверить текущую версию

```bash
kubectl get deployment affine -n affine -o jsonpath='{.spec.template.spec.containers[0].image}'
```

### Обновить до новой версии

```bash
# 1. Проверить release notes на GitHub
# https://github.com/toeverything/AFFiNE/releases

# 2. Обновить образ (использовать stable или конкретный tag)
kubectl set image deployment/affine \
  affine=ghcr.io/toeverything/affine:stable \
  -n affine

# 3. Запустить миграцию если требуется
kubectl delete job affine-migration -n affine --ignore-not-found
# Обновить версию в affine-migration.yaml
kubectl apply -f affine-migration.yaml

# 4. Дождаться миграции
kubectl wait --namespace affine \
  --for=condition=complete \
  job/affine-migration \
  --timeout=300s

# 5. Рестарт AFFiNE
kubectl rollout restart deployment/affine -n affine
kubectl rollout status deployment/affine -n affine
```

---

## Storage

AFFiNE использует [[Longhorn]] для хранения:

| PVC | Назначение | Размер |
|-----|------------|--------|
| `postgres-data` | PostgreSQL данные | 10Gi |
| `affine-storage` | Uploaded files, blobs | 20Gi |
| `affine-config` | Конфигурация | 1Gi |

```bash
kubectl get pvc -n affine
```

---

## Backup

### Полный backup

```bash
# 1. Scale down AFFiNE
kubectl scale deployment/affine -n affine --replicas=0

# 2. Backup PostgreSQL
kubectl exec -n affine deploy/postgres -- \
  pg_dump -U affine -d affine > affine_backup_$(date +%Y%m%d).sql

# 3. Backup storage через Longhorn snapshot
# UI: http://192.168.20.239 → Volumes → Create Snapshot

# 4. Scale up AFFiNE
kubectl scale deployment/affine -n affine --replicas=1
```

### Restore

```bash
# 1. Scale down
kubectl scale deployment/affine -n affine --replicas=0

# 2. Restore PostgreSQL
cat affine_backup_20260127.sql | kubectl exec -i -n affine deploy/postgres -- \
  psql -U affine -d affine

# 3. Restore storage через Longhorn (если нужно)

# 4. Scale up
kubectl scale deployment/affine -n affine --replicas=1
```

---

## Troubleshooting

### Migration Job failed

**Симптом:** Job завершился с ошибкой.

```bash
# Логи миграции
kubectl logs -n affine job/affine-migration

# Частые причины:
# - PostgreSQL не готов (проверить pg_isready)
# - Неправильный DATABASE_URL
# - Нет прав на создание таблиц
```

**Решение:** Удалить Job и запустить заново:
```bash
kubectl delete job affine-migration -n affine
kubectl apply -f affine-migration.yaml
```

### AFFiNE не запускается (CrashLoopBackOff)

**Симптом:** Pod постоянно перезапускается.

```bash
# Логи
kubectl logs -n affine -l app=affine --tail=100

# Частые причины:
# - Миграция не выполнена
# - Неправильные DATABASE_URL или REDIS credentials
# - Недостаточно памяти
```

### Не могу подключиться к AFFiNE

**Проверить:**

```bash
# 1. Pod Running?
kubectl get pods -n affine

# 2. Сервис получил IP?
kubectl get svc affine -n affine

# 3. MetalLB speaker работает?
kubectl get pods -n metallb-system

# 4. Проверить доступность
curl -I http://192.168.20.243
```

### PostgreSQL: "FATAL: password authentication failed"

**Причина:** Пароль в Secret не совпадает с паролем в PostgreSQL.

**Решение:**
```bash
# Пересоздать PostgreSQL с правильным паролем
kubectl delete deployment postgres -n affine
kubectl delete pvc postgres-data -n affine
kubectl apply -f postgres.yaml

# Перезапустить миграцию
kubectl delete job affine-migration -n affine --ignore-not-found
kubectl apply -f affine-migration.yaml
```

---

## Полезные команды

```bash
# Логи всех компонентов
kubectl logs -n affine -l app=affine --tail=50
kubectl logs -n affine -l app=postgres --tail=50
kubectl logs -n affine -l app=redis --tail=50

# Shell в AFFiNE
kubectl exec -it -n affine deploy/affine -- /bin/sh

# Shell в PostgreSQL
kubectl exec -it -n affine deploy/postgres -- psql -U affine -d affine

# Проверить Redis
kubectl exec -it -n affine deploy/redis -- redis-cli -a $REDIS_PASSWORD ping

# Рестарт AFFiNE
kubectl rollout restart deployment/affine -n affine
```

---

## Требования к ресурсам

| Компонент | CPU Request | CPU Limit | Memory Request | Memory Limit |
|-----------|-------------|-----------|----------------|--------------|
| AFFiNE | 250m | 1000m | 512Mi | 2Gi |
| PostgreSQL | 100m | 500m | 256Mi | 1Gi |
| Redis | 50m | 200m | 64Mi | 256Mi |
| **Всего** | 400m | 1700m | 832Mi | 3.25Gi |

**Рекомендации:**
- Минимум 4GB RAM на ноде для AFFiNE namespace
- SSD storage для PostgreSQL (Longhorn обеспечивает)

---

## См. также

- [[K3s]]
- [[K3s - Архитектура]] — схема взаимодействия сервисов
- [[Kubernetes - Сеть и взаимодействие]] — теория networking
- [[Longhorn]]
- [[MetalLB]]
- [[CVAT]] — похожий паттерн деплоя
- [[MinIO]] — S3 storage
- [AFFiNE Documentation](https://docs.affine.pro/self-host-affine)
- [AFFiNE GitHub](https://github.com/toeverything/AFFiNE)
- [AFFiNE Releases](https://github.com/toeverything/AFFiNE/releases)

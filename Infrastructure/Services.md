---
tags:
  - kubernetes
  - networking
created: 2026-01-19
updated: 2026-01-24
---

# Services

Kubernetes Service — абстракция для стабильного доступа к группе Pod'ов.

> Подробная теория: [[Kubernetes - Сеть и взаимодействие]]

## Зачем нужен Service?

**Проблема:** Pod'ы эфемерны — при пересоздании получают новый IP.

**Решение:** Service предоставляет:
- Стабильный IP-адрес (ClusterIP)
- DNS-имя (`<service>.<namespace>.svc.cluster.local`)
- Балансировку нагрузки между Pod'ами

```
┌─────────────────────────────────────────────────────────┐
│  Клиент                                                 │
│     │                                                   │
│     ▼                                                   │
│  ┌────────────────────────────────┐                    │
│  │  Service "my-app"              │                    │
│  │  ClusterIP: 10.43.100.50       │                    │
│  │  DNS: my-app.default.svc...    │                    │
│  │  Port: 80 → targetPort: 8080   │                    │
│  └────────────────────────────────┘                    │
│              │                                          │
│    ┌─────────┼─────────┐                               │
│    ▼         ▼         ▼                               │
│  ┌────┐   ┌────┐   ┌────┐                             │
│  │Pod1│   │Pod2│   │Pod3│  ← selector: app=my-app     │
│  └────┘   └────┘   └────┘                             │
└─────────────────────────────────────────────────────────┘
```

## Типы Service

| Тип | Доступность | Использование |
|-----|-------------|---------------|
| `ClusterIP` | Только внутри кластера | Базы данных, внутренние API |
| `NodePort` | IP_ноды:порт (30000-32767) | Простой внешний доступ |
| `LoadBalancer` | Внешний IP (через [[MetalLB]]) | Production-сервисы |
| `ExternalName` | DNS CNAME | Доступ к внешним сервисам |

### ClusterIP (по умолчанию)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: postgres
spec:
  type: ClusterIP  # можно не указывать
  selector:
    app: postgres
  ports:
    - port: 5432
      targetPort: 5432
```

### NodePort

```yaml
apiVersion: v1
kind: Service
metadata:
  name: web
spec:
  type: NodePort
  selector:
    app: web
  ports:
    - port: 80
      targetPort: 8080
      nodePort: 30080  # опционально, иначе автоматически
```

### LoadBalancer

```yaml
apiVersion: v1
kind: Service
metadata:
  name: api
spec:
  type: LoadBalancer
  selector:
    app: api
  ports:
    - port: 80
      targetPort: 8080
```

## Три порта Service

| Порт | Где определён | Описание |
|------|---------------|----------|
| `port` | Service | Порт, на котором Service принимает трафик |
| `targetPort` | Pod | Порт, куда Service отправляет трафик |
| `nodePort` | Node | Порт на каждой ноде (только NodePort/LB) |

```yaml
ports:
  - port: 80          # Клиент → Service:80
    targetPort: 8080  # Service → Pod:8080
    nodePort: 30080   # Внешний → Node:30080 → Service:80 → Pod:8080
```

## Labels и Selectors

Service находит Pod'ы по меткам:

```yaml
# Pod
metadata:
  labels:
    app: my-app
    version: v2

# Service
spec:
  selector:
    app: my-app  # выбирает все Pod'ы с app=my-app
```

```bash
# Проверить, какие Pod'ы выбрал Service
kubectl get endpoints my-app
```

## DNS-имена

Каждый Service получает DNS-запись:

```
<service>.<namespace>.svc.cluster.local
```

**Примеры из кластера:**

| Service | Namespace | DNS |
|---------|-----------|-----|
| minio | minio | `minio.minio.svc.cluster.local` |
| cvat-backend-server | cvat | `cvat-backend-server.cvat.svc.cluster.local` |
| postgres | cvat | `postgres.cvat.svc.cluster.local` |

**Cross-namespace доступ:**
```bash
# Из namespace cvat к minio:
curl http://minio.minio:80  # с namespace
curl http://minio.minio.svc.cluster.local:80  # полный FQDN
```

## Практические команды

```bash
# Список сервисов
kubectl get svc -A

# Детали сервиса
kubectl describe svc <name> -n <namespace>

# Endpoints (к каким Pod'ам ведёт)
kubectl get endpoints <name> -n <namespace>

# Создать Service для Deployment
kubectl expose deployment nginx --port=80 --type=LoadBalancer

# Проверить порты Pod'а
kubectl exec -n <namespace> <pod> -- ss -tlnp

# Изменить targetPort
kubectl patch svc <name> -n <namespace> --type=json \
  -p='[{"op":"replace","path":"/spec/ports/0/targetPort","value":8080}]'
```

## Сервисы в нашем кластере

| Service | Namespace | Type | IP | Port |
|---------|-----------|------|-----|------|
| minio | minio | LoadBalancer | 192.168.20.237 | 80 |
| minio-console | minio | LoadBalancer | 192.168.20.238 | 80 |
| cvat-backend-server | cvat | ClusterIP | — | 8080 |
| cvat-nuclio-dashboard | cvat | LoadBalancer | 192.168.20.236 | 80 |
| clearml-apiserver | clearml | LoadBalancer | 192.168.20.242 | 80 |

## Troubleshooting

### Endpoints пустой

```bash
kubectl get endpoints my-service
# NAME         ENDPOINTS
# my-service   <none>
```

**Причина:** Selector не находит Pod'ы.

**Решение:**
```bash
# Проверить labels Pod'ов
kubectl get pods --show-labels

# Проверить selector Service
kubectl get svc my-service -o jsonpath='{.spec.selector}'
```

### Неправильный targetPort

**Симптом:** Connection refused.

```bash
# На каком порту слушает Pod?
kubectl exec <pod> -- ss -tlnp

# Исправить targetPort
kubectl patch svc <service> --type=json \
  -p='[{"op":"replace","path":"/spec/ports/0/targetPort","value":CORRECT_PORT}]'
```

### LoadBalancer Pending

```bash
kubectl get svc my-service
# NAME         TYPE           EXTERNAL-IP
# my-service   LoadBalancer   <pending>
```

**Причина:** Нет LoadBalancer controller.

**Решение:** Установить [[MetalLB]].

## См. также

- [[Kubernetes - Сеть и взаимодействие]] — подробная теория
- [[Kubernetes]]
- [[K3s]]
- [[Deployments]]
- [[Ingress]]
- [[MetalLB]]

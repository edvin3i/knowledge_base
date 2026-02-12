---
tags:
  - kubernetes
  - networking
  - theory
  - infrastructure
created: 2026-01-24
---

# Kubernetes: Сеть и взаимодействие компонентов

Подробное руководство для новичков о том, как Pod'ы, Service'ы и Namespace'ы взаимодействуют друг с другом.

## Оглавление

1. [[#Сетевая модель Kubernetes]]
2. [[#Pod: Минимальная единица]]
3. [[#Service: Стабильная точка доступа]]
4. [[#Namespace: Логическая изоляция]]
5. [[#DNS в Kubernetes]]
6. [[#Практические примеры из кластера]]

---

## Сетевая модель Kubernetes

### Основные принципы

Kubernetes построен на нескольких фундаментальных сетевых принципах:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     СЕТЕВАЯ МОДЕЛЬ KUBERNETES                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. Каждый Pod получает уникальный IP-адрес в кластере                  │
│                                                                          │
│  2. Все Pod'ы могут общаться друг с другом напрямую (без NAT)          │
│                                                                          │
│  3. Все ноды могут общаться со всеми Pod'ами без NAT (и наоборот)      │
│                                                                          │
│  4. IP, который Pod видит у себя, совпадает с IP, который              │
│     видят другие (нет скрытого NAT)                                     │
│                                                                          │
│  Следствие: Service предоставляет стабильный IP/DNS                     │
│  для группы Pod'ов                                                      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Что это значит на практике?

**Без Kubernetes (традиционный подход):**
- Нужно вручную настраивать IP-адреса
- Нужно пробрасывать порты между контейнерами
- При перезапуске контейнера IP может измениться

**С Kubernetes:**
- Каждый Pod автоматически получает IP
- Pod'ы "видят" друг друга напрямую
- Service обеспечивает стабильный адрес, даже если Pod'ы пересоздаются

---

## Pod: Минимальная единица

### Что такое Pod?

**Pod** — это минимальная единица развёртывания в Kubernetes. Это НЕ контейнер, а обёртка вокруг одного или нескольких контейнеров.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              POD                                         │
│                         IP: 10.42.0.15                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    │
│   │   Container 1   │    │   Container 2   │    │   Container 3   │    │
│   │   (nginx)       │    │   (php-fpm)     │    │   (log-agent)   │    │
│   │   порт 80       │    │   порт 9000     │    │   ---           │    │
│   └─────────────────┘    └─────────────────┘    └─────────────────┘    │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │              ОБЩИЕ РЕСУРСЫ (shared namespace)                    │  │
│   │  • Сетевой namespace (один IP для всех контейнеров)             │  │
│   │  • Volumes (общее хранилище)                                     │  │
│   │  • IPC namespace (межпроцессное взаимодействие)                 │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Ключевые особенности Pod

#### 1. Общий сетевой namespace

Все контейнеры внутри одного Pod:
- Имеют **один и тот же IP-адрес**
- Могут общаться через `localhost`
- Делят пространство портов (нельзя двум контейнерам слушать один порт)

```bash
# Пример: контейнеры внутри Pod'а общаются через localhost
# Container 1 (nginx) слушает на порту 80
# Container 2 (php-fpm) слушает на порту 9000

# nginx может обратиться к php-fpm так:
# fastcgi_pass localhost:9000;
```

#### 2. Уникальный IP в кластере

```bash
# Посмотреть IP-адреса Pod'ов
kubectl get pods -o wide

# Пример вывода:
# NAME                    READY   STATUS    IP           NODE
# cvat-backend-server-0   1/1     Running   10.42.0.15   polynode-1
# minio-0                 1/1     Running   10.42.1.23   polynode-2
```

#### 3. Эфемерность

Pod'ы — **временные**. Они могут быть:
- Пересозданы при обновлении
- Перенесены на другую ноду
- Удалены и заменены новыми

**Важно:** При пересоздании Pod получает **новый IP-адрес**!

```
    Pod v1 (IP: 10.42.0.15)     →     Pod v2 (IP: 10.42.0.89)
         [удалён]                         [создан]
              ↓                               ↓
    Старый IP больше            Новый IP, который нужно
    не существует               как-то узнать...
```

**Проблема:** Как другим приложениям узнать новый IP?

**Решение:** Service!

---

## Service: Стабильная точка доступа

### Зачем нужен Service?

Service решает проблему эфемерности Pod'ов. Он предоставляет:
- **Стабильный IP-адрес** (ClusterIP), который не меняется
- **DNS-имя** для обращения по имени
- **Балансировку нагрузки** между несколькими Pod'ами

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         КАК РАБОТАЕТ SERVICE                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Клиент                                                                │
│      │                                                                   │
│      │ Запрос к minio.minio.svc.cluster.local:80                        │
│      ▼                                                                   │
│   ┌──────────────────────────────────────┐                              │
│   │           SERVICE "minio"            │                              │
│   │         ClusterIP: 10.43.150.23      │                              │
│   │              Port: 80                │                              │
│   │                                      │                              │
│   │   selector: app=minio                │ ← Выбирает Pod'ы            │
│   └──────────────────────────────────────┘   по меткам                  │
│           │                                                              │
│           │ Перенаправляет на targetPort                                │
│           ▼                                                              │
│   ┌─────────────────┐                                                   │
│   │   Pod "minio-0" │                                                   │
│   │   IP: 10.42.1.23│                                                   │
│   │   Port: 9000    │ ← targetPort                                      │
│   └─────────────────┘                                                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Три ключевых порта

При работе с Service важно понимать разницу между портами:

| Порт | Где | Описание |
|------|-----|----------|
| **port** | Service | Порт, на котором Service принимает запросы |
| **targetPort** | Pod | Порт, на который Service перенаправляет запросы |
| **nodePort** | Нода | (только для NodePort) Порт на каждой ноде кластера |

```yaml
# Пример: MinIO Service
apiVersion: v1
kind: Service
metadata:
  name: minio
  namespace: minio
spec:
  type: LoadBalancer
  selector:
    app: minio          # ← Выбирает Pod'ы с меткой app=minio
  ports:
    - port: 80          # ← Клиенты обращаются на порт 80
      targetPort: 9000  # ← Запросы идут на порт 9000 Pod'а
```

**Практический пример:**

```bash
# Клиент делает запрос:
curl http://minio.minio.svc.cluster.local:80/

# Service получает запрос на порт 80
# и перенаправляет на Pod minio-0 порт 9000
```

### Типы Service

#### 1. ClusterIP (по умолчанию)

Доступен **только внутри кластера**.

```yaml
spec:
  type: ClusterIP  # или не указывать — это default
```

```
┌─────────────────── Кластер ───────────────────┐
│                                                │
│  Pod A ──────► ClusterIP ──────► Pod B        │
│               10.43.x.x                        │
│                                                │
└────────────────────────────────────────────────┘
     ↑
  Внешний мир НЕ имеет доступа
```

**Когда использовать:** Для внутренних сервисов (базы данных, кэши, бэкенды).

#### 2. NodePort

Открывает порт на **каждой ноде** кластера (диапазон 30000-32767).

```yaml
spec:
  type: NodePort
  ports:
    - port: 80
      targetPort: 8080
      nodePort: 30080  # ← Порт на всех нодах
```

```
┌─────────────────── Кластер ───────────────────┐
│                                                │
│   polynode-1:30080 ─┐                          │
│   polynode-2:30080 ─┼──► Service ──► Pods     │
│   polynode-3:30080 ─┘                          │
│                                                │
└────────────────────────────────────────────────┘
         ↑
   Внешний доступ через IP_НОДЫ:30080
```

**Когда использовать:** Простой внешний доступ без LoadBalancer.

#### 3. LoadBalancer

Запрашивает внешний IP у облачного провайдера или [[MetalLB]].

```yaml
spec:
  type: LoadBalancer
```

```
┌─────────────────── Кластер ───────────────────┐
│                                                │
│   External IP: 192.168.20.237 (от MetalLB)    │
│          │                                     │
│          ▼                                     │
│      Service ──────────────► Pods             │
│                                                │
└────────────────────────────────────────────────┘
         ↑
   Внешний доступ через стабильный IP
```

**Когда использовать:** Production-сервисы, доступные извне.

### Как Service находит Pod'ы? Labels и Selectors

Service использует **labels** (метки) для поиска Pod'ов:

```yaml
# Pod с метками
apiVersion: v1
kind: Pod
metadata:
  name: my-app
  labels:
    app: my-app        # ← Метка 1
    version: v2        # ← Метка 2
spec:
  containers:
    - name: app
      image: my-app:v2
---
# Service, который выбирает Pod'ы по меткам
apiVersion: v1
kind: Service
metadata:
  name: my-app-service
spec:
  selector:
    app: my-app        # ← Выбирает все Pod'ы с app=my-app
  ports:
    - port: 80
      targetPort: 8080
```

```bash
# Посмотреть Endpoints (какие Pod'ы выбрал Service)
kubectl get endpoints my-app-service

# NAME              ENDPOINTS
# my-app-service    10.42.0.15:8080,10.42.1.23:8080
```

---

## Namespace: Логическая изоляция

### Что такое Namespace?

**Namespace** — это способ разделить кластер на виртуальные подкластеры.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         KUBERNETES CLUSTER                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │  namespace:     │  │  namespace:     │  │  namespace:     │         │
│  │  cvat           │  │  minio          │  │  clearml        │         │
│  ├─────────────────┤  ├─────────────────┤  ├─────────────────┤         │
│  │ • cvat-backend  │  │ • minio         │  │ • apiserver     │         │
│  │ • cvat-frontend │  │ • minio-console │  │ • webserver     │         │
│  │ • postgres      │  │                 │  │ • mongodb       │         │
│  │ • redis         │  │                 │  │ • redis         │         │
│  │ • nuclio        │  │                 │  │ • elasticsearch │         │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘         │
│                                                                          │
│  ┌─────────────────┐  ┌─────────────────┐                               │
│  │  namespace:     │  │  namespace:     │                               │
│  │  longhorn-system│  │  kube-system    │                               │
│  ├─────────────────┤  ├─────────────────┤                               │
│  │ • longhorn-mgr  │  │ • coredns       │                               │
│  │ • longhorn-ui   │  │ • traefik       │                               │
│  │ • csi-driver    │  │ • metrics-server│                               │
│  └─────────────────┘  └─────────────────┘                               │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Зачем нужны Namespace'ы?

1. **Организация** — группировка связанных ресурсов
2. **Изоляция имён** — в разных namespace'ах могут быть одинаковые имена
3. **Разграничение доступа** — RBAC политики на уровне namespace
4. **Квоты ресурсов** — лимиты CPU/RAM на namespace

### Namespace и DNS

Когда создаётся Service, он получает DNS-запись:

```
<service-name>.<namespace>.svc.cluster.local
```

**Примеры из нашего кластера:**

| Service | Namespace | Полный DNS |
|---------|-----------|------------|
| minio | minio | `minio.minio.svc.cluster.local` |
| cvat-backend-server | cvat | `cvat-backend-server.cvat.svc.cluster.local` |
| clearml-apiserver | clearml | `clearml-apiserver.clearml.svc.cluster.local` |

---

## DNS в Kubernetes

### Как работает DNS

Kubernetes запускает DNS-сервер (CoreDNS), который автоматически:
- Регистрирует DNS-записи для всех Service'ов
- Отвечает на DNS-запросы от Pod'ов

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DNS RESOLUTION                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Pod в namespace "cvat"                                                │
│   хочет обратиться к MinIO                                              │
│                                                                          │
│   Вариант 1: Короткое имя (в том же namespace)                          │
│   ───────────────────────────────────────────                           │
│   nslookup redis                                                        │
│   → Ищет redis.cvat.svc.cluster.local                                   │
│   → Находит: 10.43.100.15                                               │
│                                                                          │
│   Вариант 2: С указанием namespace                                      │
│   ─────────────────────────────────                                     │
│   nslookup minio.minio                                                  │
│   → Ищет minio.minio.svc.cluster.local                                  │
│   → Находит: 10.43.150.23                                               │
│                                                                          │
│   Вариант 3: Полный FQDN                                                │
│   ─────────────────────                                                 │
│   nslookup minio.minio.svc.cluster.local                                │
│   → Находит: 10.43.150.23                                               │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Правила резолвинга DNS

```yaml
# Короткое имя: <service>
# Работает только внутри того же namespace!
curl http://postgres:5432

# С namespace: <service>.<namespace>
# Работает из любого namespace
curl http://minio.minio:80

# Полный FQDN: <service>.<namespace>.svc.cluster.local
# Однозначно, всегда работает
curl http://minio.minio.svc.cluster.local:80
```

### Важно: Cross-namespace коммуникация

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CROSS-NAMESPACE COMMUNICATION                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   namespace: cvat                      namespace: minio                  │
│  ┌─────────────────┐                  ┌─────────────────┐               │
│  │ cvat-backend    │   HTTP Request   │     minio       │               │
│  │                 │ ───────────────► │                 │               │
│  │                 │                  │                 │               │
│  └─────────────────┘                  └─────────────────┘               │
│                                                                          │
│   Как обратиться:                                                       │
│   ✗ curl http://minio:80              ← Не работает! (ищет в cvat)     │
│   ✓ curl http://minio.minio:80        ← Работает                       │
│   ✓ curl http://minio.minio.svc.cluster.local:80  ← Работает           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Практическая проверка DNS:**

```bash
# Запустить Pod для тестирования
kubectl run dnstest --image=busybox --rm -it --restart=Never -- sh

# Внутри Pod'а:
nslookup minio.minio
# Server:    10.43.0.10
# Address 1: 10.43.0.10 kube-dns.kube-system.svc.cluster.local
# Name:      minio.minio
# Address 1: 10.43.150.23 minio.minio.svc.cluster.local
```

---

## Практические примеры из кластера

### Пример 1: CVAT обращается к MinIO

**Сценарий:** CVAT хранит аннотации в MinIO.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                           │
│   namespace: cvat                         namespace: minio                │
│  ┌───────────────────────┐              ┌──────────────────────┐         │
│  │  cvat-backend-server  │              │   minio (Service)    │         │
│  │                       │              │   ClusterIP          │         │
│  │  Env:                 │   S3 API    │   Port: 80           │         │
│  │  AWS_S3_ENDPOINT_URL= │ ──────────► │   targetPort: 9000   │         │
│  │  http://192.168.20.237│              │                      │         │
│  │                       │              │   или internal:      │         │
│  │  Или internal:        │              │   minio.minio:80     │         │
│  │  http://minio.minio:80│              │                      │         │
│  └───────────────────────┘              └──────────┬───────────┘         │
│                                                     │                     │
│                                                     ▼                     │
│                                          ┌──────────────────────┐        │
│                                          │   minio-0 (Pod)      │        │
│                                          │   IP: 10.42.1.23     │        │
│                                          │   Port: 9000         │        │
│                                          └──────────────────────┘        │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

**Конфигурация в CVAT:**

```yaml
env:
  - name: AWS_S3_ENDPOINT_URL
    value: "http://minio.minio.svc.cluster.local:80"
  # или через LoadBalancer IP:
  # value: "http://192.168.20.237"
```

### Пример 2: CVAT обращается к Nuclio

**Сценарий:** CVAT запрашивает список моделей у Nuclio Dashboard.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         namespace: cvat                                   │
│                                                                           │
│  ┌───────────────────────┐          ┌──────────────────────────┐         │
│  │  cvat-backend-server  │          │  nuclio-dashboard        │         │
│  │                       │          │  (Service)               │         │
│  │  Env:                 │  HTTP    │  Port: 80                │         │
│  │  CVAT_NUCLIO_HOST=    │ ───────► │  targetPort: 8070        │         │
│  │  cvat-nuclio-dashboard│          │                          │         │
│  │  CVAT_NUCLIO_PORT=80  │          └──────────┬───────────────┘         │
│  │                       │                      │                         │
│  └───────────────────────┘                      ▼                         │
│                                       ┌──────────────────────────┐        │
│                                       │  nuclio-dashboard (Pod)  │        │
│                                       │  Port: 8070              │        │
│                                       └──────────────────────────┘        │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

**Важный момент:**
- Service слушает на **порту 80**
- Pod слушает на **порту 8070**
- Service перенаправляет 80 → 8070

```bash
# Проверить маппинг портов
kubectl get svc cvat-nuclio-dashboard -n cvat
# NAME                    TYPE           PORT(S)
# cvat-nuclio-dashboard   LoadBalancer   80:31234/TCP

kubectl get endpoints cvat-nuclio-dashboard -n cvat
# NAME                    ENDPOINTS
# cvat-nuclio-dashboard   10.42.0.45:8070
```

### Пример 3: Nuclio вызывает функцию для аннотации

**Сценарий:** При автоаннотации Nuclio Dashboard вызывает serverless-функцию.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         namespace: cvat                                   │
│                                                                           │
│  ┌─────────────┐     ┌───────────────────┐     ┌──────────────────────┐  │
│  │ cvat-worker │     │ nuclio-dashboard  │     │ nuclio-function      │  │
│  │ annotation  │     │                   │     │ yolo11-detector      │  │
│  │             │────►│ Получает запрос   │────►│                      │  │
│  │ POST /api/  │     │ на инференс       │     │ Service              │  │
│  │ functions/  │     │                   │     │ (ClusterIP)          │  │
│  │ invoke      │     │ Находит функцию   │     │ Port: 8080           │  │
│  └─────────────┘     │ и вызывает её     │     └──────────┬───────────┘  │
│                      │ по internal URL:  │                │              │
│                      │ nuclio-yolo...    │                ▼              │
│                      │ .cvat.svc:8080    │     ┌──────────────────────┐  │
│                      └───────────────────┘     │ Function Pod         │  │
│                                                │ Port: 8080           │  │
│                                                │ + GPU                │  │
│                                                └──────────────────────┘  │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

**Ключевой момент:** `internalInvocationUrls`

Nuclio Dashboard должен знать, как вызвать функцию. Для этого функция должна иметь:

```yaml
# В function.yaml
triggers:
  myHttpTrigger:
    kind: http
    attributes:
      serviceType: ClusterIP  # ← Критически важно!
```

После деплоя Nuclio создаёт Service и сохраняет URL:

```bash
kubectl get nucliofunctions.nuclio.io -n cvat -o yaml
# status:
#   internalInvocationUrls:
#     - "nuclio-yolo11x-cvat-detector-gpu.cvat.svc.cluster.local:8080"
```

### Пример 4: ClearML агент получает задачи

**Сценарий:** ClearML Agent (на GPU-ноде) опрашивает API-сервер на наличие задач.

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                           │
│  ┌─────────────────────────────────┐    ┌───────────────────────────────┐│
│  │  polydev-desktop (GPU node)     │    │  namespace: clearml           ││
│  │                                 │    │                               ││
│  │  ┌─────────────────────────┐   │    │  ┌─────────────────────────┐  ││
│  │  │  clearml-agent          │   │    │  │  clearml-apiserver      │  ││
│  │  │                         │   │    │  │  (Service)              │  ││
│  │  │  Config:                │   │    │  │  LoadBalancer           │  ││
│  │  │  api_server:            │───┼────┼─►│  IP: 192.168.20.242     │  ││
│  │  │  192.168.20.242         │   │    │  │  Port: 80               │  ││
│  │  │                         │   │    │  │  targetPort: 8008       │  ││
│  │  └─────────────────────────┘   │    │  └───────────┬─────────────┘  ││
│  │                                 │    │              │                ││
│  └─────────────────────────────────┘    │              ▼                ││
│                                         │  ┌─────────────────────────┐  ││
│                                         │  │  apiserver Pod          │  ││
│                                         │  │  Port: 8008             │  ││
│                                         │  └─────────────────────────┘  ││
│                                         │                               ││
│                                         └───────────────────────────────┘│
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

**Конфигурация агента (`~/clearml.conf`):**

```hocon
api {
    api_server: http://192.168.20.242  # LoadBalancer IP
    web_server: http://192.168.20.240
    files_server: http://192.168.20.241
}
```

---

## Диагностика сетевых проблем

### Полезные команды

```bash
# 1. Проверить, что Pod запущен и имеет IP
kubectl get pods -o wide -n <namespace>

# 2. Проверить Service и его Endpoints
kubectl get svc -n <namespace>
kubectl get endpoints <service-name> -n <namespace>

# 3. Проверить, на каком порту слушает Pod
kubectl exec -n <namespace> <pod> -- ss -tlnp
# или
kubectl exec -n <namespace> <pod> -- netstat -tlnp

# 4. Проверить DNS резолвинг
kubectl run dnstest --image=busybox --rm -it --restart=Never -- \
  nslookup <service>.<namespace>

# 5. Проверить доступность сервиса
kubectl run curltest --image=curlimages/curl --rm -it --restart=Never -- \
  curl -v http://<service>.<namespace>:<port>/

# 6. Посмотреть логи Pod'а
kubectl logs -n <namespace> <pod> --tail=100

# 7. Детальная информация о Service
kubectl describe svc <service-name> -n <namespace>
```

### Частые проблемы

#### Проблема: Service не находит Pod'ы

```bash
kubectl get endpoints <service> -n <namespace>
# Если ENDPOINTS пустой — проблема с selector'ами

# Проверить labels Pod'а
kubectl get pod <pod> -n <namespace> --show-labels

# Проверить selector Service'а
kubectl get svc <service> -n <namespace> -o jsonpath='{.spec.selector}'
```

#### Проблема: Неправильный targetPort

```bash
# Service отправляет на targetPort, но Pod слушает на другом

# Проверить, на чём слушает Pod:
kubectl exec -n <namespace> <pod> -- ss -tlnp

# Исправить targetPort в Service:
kubectl patch svc <service> -n <namespace> --type=json \
  -p='[{"op":"replace","path":"/spec/ports/0/targetPort","value":<correct-port>}]'
```

#### Проблема: Cross-namespace доступ не работает

```bash
# Используйте полное имя с namespace:
curl http://service.namespace.svc.cluster.local:port

# Вместо короткого:
curl http://service:port  # ← Не работает из другого namespace!
```

---

## Резюме

### Ключевые концепции

| Концепция | Описание |
|-----------|----------|
| **Pod IP** | Уникальный, но временный. Меняется при пересоздании |
| **Service ClusterIP** | Стабильный внутренний IP. Не меняется |
| **Service DNS** | `<service>.<namespace>.svc.cluster.local` |
| **targetPort** | Порт, на котором слушает Pod |
| **port** | Порт, на котором слушает Service |
| **Namespace** | Логическая изоляция. Влияет на DNS |

### Правила для новичка

1. **Используйте Service**, а не Pod IP напрямую
2. **Указывайте namespace** при cross-namespace доступе
3. **Проверяйте targetPort** — частая причина ошибок
4. **Смотрите Endpoints** — если пусто, selector не находит Pod'ы
5. **Используйте DNS**, а не IP где возможно

---

## См. также

- [[Kubernetes]] — основные концепции
- [[K3s]] — наш кластер
- [[K3s - Архитектура]] — топология кластера
- [[Services]] — детали о типах сервисов
- [[MetalLB]] — LoadBalancer для bare-metal
- [[Networking]] — сетевые концепции
- [Kubernetes Networking Model](https://kubernetes.io/docs/concepts/services-networking/)

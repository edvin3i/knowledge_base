---
tags:
  - kubernetes
  - networking
  - infrastructure
created: 2026-01-20
---

# MetalLB

Load Balancer для bare-metal Kubernetes кластеров. Позволяет сервисам типа `LoadBalancer` получать внешние IP адреса.

## Теория: Что такое MetalLB

### Проблема

В облачных Kubernetes (AWS, GCP, Azure) сервисы типа `LoadBalancer` автоматически получают внешний IP от облачного провайдера.

В bare-metal кластерах (как наш [[K3s]]) такой функциональности нет — `EXTERNAL-IP` остаётся в состоянии `<pending>` навсегда.

```
# Без MetalLB
kubectl get svc traefik -n kube-system
NAME      TYPE           EXTERNAL-IP
traefik   LoadBalancer   <pending>     ← Никогда не получит IP

# С MetalLB
kubectl get svc traefik -n kube-system
NAME      TYPE           EXTERNAL-IP
traefik   LoadBalancer   192.168.20.235   ← IP из пула MetalLB
```

### Решение

**MetalLB** эмулирует облачный LoadBalancer:
1. Следит за сервисами типа `LoadBalancer`
2. Выделяет IP из заданного пула
3. Анонсирует этот IP в локальной сети (L2 или BGP)

### Режимы работы

| Режим | Протокол | Когда использовать |
|-------|----------|-------------------|
| **L2 (Layer 2)** | ARP/NDP | Простые сети, домашние лабы |
| **BGP** | BGP | Продакшн, интеграция с роутерами |

**L2 режим** (используем):
- MetalLB отвечает на ARP запросы для выделенных IP
- Не требует настройки роутера
- Ограничение: весь трафик идёт через одну ноду (leader)
- Требует порт **7946/tcp+udp** между нодами (memberlist)

**Выбор лидера (stateless hash):**
Каждый speaker вычисляет `hash(nodeName + serviceIP)`, сортирует результаты, и первый в списке становится лидером для данного Service IP. При падении ноды memberlist определяет недоступность, и все speakers пересчитывают hash без этой ноды — новый лидер отправляет gratuitous ARP.

```
┌─────────────────────────────────────────────────────────────┐
│                    L2 Mode Architecture                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   Client                                                     │
│      │                                                       │
│      │ "Who has 192.168.20.235?"                            │
│      ▼                                                       │
│   ┌─────────────────────────────────────────────┐           │
│   │              Local Network                   │           │
│   └─────────────────────────────────────────────┘           │
│      │                    │                    │             │
│      ▼                    ▼                    ▼             │
│   ┌──────┐           ┌──────┐           ┌──────┐            │
│   │node-1│           │node-2│           │node-3│            │
│   │      │           │      │           │      │            │
│   │speak-│◄──────────│speak-│           │speak-│            │
│   │  er  │  leader   │  er  │           │  er  │            │
│   └──────┘           └──────┘           └──────┘            │
│      │                                                       │
│      │ "I have 192.168.20.235!" (ARP reply)                 │
│      ▼                                                       │
│   Traffic goes to node-1, then kube-proxy                   │
│   distributes to actual pods                                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Статус

| Параметр | Значение |
|----------|----------|
| **Версия** | v0.15.3 |
| **Namespace** | `metallb-system` |
| **Режим** | L2 |
| **IP пул** | 192.168.20.235-192.168.20.249 |

---

## Установка

### 1. Применить манифесты

```bash
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.15.3/config/manifests/metallb-native.yaml
```

### 2. Дождаться готовности

```bash
kubectl wait --namespace metallb-system \
  --for=condition=ready pod \
  --selector=app=metallb \
  --timeout=120s
```

### 3. Настроить IP пул

Выбрать свободный диапазон IP в локальной сети (не пересекающийся с DHCP):

```bash
kubectl apply -f - << 'EOF'
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: default-pool
  namespace: metallb-system
spec:
  addresses:
  - 192.168.20.235-192.168.20.249
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: default
  namespace: metallb-system
EOF
```

### 4. Проверка

```bash
# MetalLB поды
kubectl get pods -n metallb-system

# Должен показать:
# controller-xxx   Running
# speaker-xxx      Running (на каждой ноде)

# Проверить что Traefik получил IP
kubectl get svc -n kube-system traefik
```

---

## Конфигурация

### IPAddressPool

Определяет диапазон IP адресов для выделения:

```yaml
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: default-pool
  namespace: metallb-system
spec:
  addresses:
  - 192.168.20.235-192.168.20.249   # Диапазон
  # или
  - 192.168.20.100/32               # Один IP
  # или
  - 192.168.30.0/24                 # Вся подсеть
```

### L2Advertisement

Указывает какие пулы анонсировать через L2:

```yaml
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: default
  namespace: metallb-system
spec:
  ipAddressPools:
  - default-pool          # Если не указано — все пулы
  interfaces:
  - eth0                  # Если не указано — все интерфейсы
```

### Несколько пулов

```yaml
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: production
  namespace: metallb-system
spec:
  addresses:
  - 192.168.20.235-192.168.20.240
---
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: development
  namespace: metallb-system
spec:
  addresses:
  - 192.168.20.241-192.168.20.245
```

Использование конкретного пула:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-service
  annotations:
    metallb.io/address-pool: production  # Deprecated: metallb.universe.tf/address-pool
spec:
  type: LoadBalancer
```

---

## Управление

### Просмотр конфигурации

```bash
# IP пулы
kubectl get ipaddresspools -n metallb-system

# L2 анонсы
kubectl get l2advertisements -n metallb-system

# Какие сервисы получили IP
kubectl get svc -A -o wide | grep LoadBalancer
```

### Редактирование

```bash
# Изменить пул IP
kubectl edit ipaddresspool default-pool -n metallb-system
```

### Логи

```bash
# Controller (выделение IP)
kubectl logs -n metallb-system -l app.kubernetes.io/component=controller

# Speaker (L2/BGP анонсы)
kubectl logs -n metallb-system -l app.kubernetes.io/component=speaker
```

---

## Troubleshooting

### Сервис не получает IP

**Симптом:** `EXTERNAL-IP` остаётся `<pending>`.

**Проверить:**

```bash
# MetalLB поды работают?
kubectl get pods -n metallb-system

# Есть свободные IP в пуле?
kubectl get ipaddresspool -n metallb-system -o yaml

# События сервиса
kubectl describe svc <service-name>
```

**Частые причины:**
- Пул IP исчерпан
- L2Advertisement не создан
- Speaker не запущен на нодах

### IP недоступен из сети

**Симптом:** Ping/curl на выделенный IP не работает.

**Проверить:**

```bash
# Какая нода отвечает за IP?
kubectl logs -n metallb-system -l app.kubernetes.io/component=speaker | grep "leader"

# ARP таблица на клиенте
arp -a | grep 192.168.20.235
```

**Частые причины:**
- Firewall на ноде блокирует трафик
- IP конфликтует с другим устройством в сети
- Сетевой интерфейс в spec.interfaces не существует

### После обновления MetalLB IP изменился

MetalLB не гарантирует стабильность IP при рестарте. Для фиксации IP:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: my-service
  annotations:
    metallb.io/loadBalancerIPs: 192.168.20.235  # Запросить конкретный IP
spec:
  type: LoadBalancer
  # Deprecated: spec.loadBalancerIP — используйте аннотацию выше
```

---

## Обновление

```bash
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.15.3/config/manifests/metallb-native.yaml
```

Конфигурация (IPAddressPool, L2Advertisement) сохраняется.

---

## Миграция с ConfigMap (v0.12 и ниже)

Старые версии MetalLB использовали ConfigMap. С v0.13+ только CRD.

**Старый формат (не работает):**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: config
  namespace: metallb-system
data:
  config: |
    address-pools:
    - name: default
      protocol: layer2
      addresses:
      - 192.168.20.235-192.168.20.249
```

**Новый формат (v0.13+):**
```yaml
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: default-pool
  namespace: metallb-system
spec:
  addresses:
  - 192.168.20.235-192.168.20.249
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: default
  namespace: metallb-system
```

---

## См. также

- [[K3s]]
- [[CVAT]] — использует MetalLB для Ingress
- [MetalLB Documentation](https://metallb.universe.tf/)
- [MetalLB GitHub](https://github.com/metallb/metallb)

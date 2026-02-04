---
tags:
  - k3s
  - networking
  - ha
created: 2025-01-15
updated: 2026-01-19
---

# kube-vip

Virtual IP для отказоустойчивого доступа к [[K3s]] API Server.

## Теория: Зачем нужен Virtual IP

### Проблема: Single Point of Failure

```
┌──────────────────────────────────────────────────────────────┐
│                    БЕЗ VIP (плохо)                           │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│   kubectl ──────► Node 1 (192.168.20.221)                    │
│                       │                                       │
│                       X  Node 1 падает                       │
│                       │                                       │
│   kubectl ──────► ???  Клиент не знает про Node 2/3          │
│                                                               │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                    С VIP (хорошо)                             │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│   kubectl ──────► VIP (192.168.20.225)                       │
│                       │                                       │
│                   ┌───┴───┐                                   │
│                   ▼       ▼                                   │
│               Node 1   Node 2   Node 3                       │
│               (лидер)                                         │
│                   │                                           │
│                   X  Node 1 падает                           │
│                   │                                           │
│                   ▼                                           │
│               Node 2 становится лидером                      │
│               VIP переезжает на Node 2                       │
│                                                               │
│   kubectl ──────► VIP ──────► Node 2                         │
│                       (тот же адрес!)                        │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

**VIP (Virtual IP)** — IP адрес, не привязанный к конкретной машине. Может "переезжать" между нодами.

### Как VIP работает на уровне сети

**ARP (Address Resolution Protocol)** — протокол для получения MAC-адреса по IP.

```
1. Клиент хочет подключиться к 192.168.20.225
2. Клиент отправляет ARP-запрос: "Кто владеет 192.168.20.225?"
3. kube-vip лидер отвечает: "Я! Мой MAC: aa:bb:cc:dd:ee:ff"
4. Клиент отправляет пакеты на этот MAC
```

При failover:
```
1. Старый лидер падает
2. Новый лидер отправляет Gratuitous ARP
3. "192.168.20.225 теперь у меня, MAC: 11:22:33:44:55:66"
4. Роутеры/свитчи обновляют ARP-таблицы
5. Трафик идёт на нового лидера
```

### Leader Election — выборы лидера

kube-vip использует Kubernetes Lease для выборов:

```
┌────────────────────────────────────────────────────────────┐
│                     Leader Election                         │
├────────────────────────────────────────────────────────────┤
│                                                             │
│   Node 1: "Я хочу быть лидером"                            │
│   Node 2: "Я тоже"                                          │
│   Node 3: "И я"                                             │
│                                                             │
│   Kubernetes Lease: "Node 1 первый, он лидер"              │
│                                                             │
│   Node 1: Добавляет VIP, отвечает на ARP                   │
│   Node 2: Ждёт, мониторит лидера                           │
│   Node 3: Ждёт, мониторит лидера                           │
│                                                             │
│   Lease: Обновляется каждые N секунд                       │
│   Если лидер не обновил — новые выборы                     │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

**Lease** — Kubernetes объект для distributed locking и leader election.

---

## Моя конфигурация

| Параметр | Значение |
|----------|----------|
| **VIP** | `192.168.20.225` |
| **Interface** | `enp1s0` |
| **Mode** | ARP + Leader Election |
| **Version** | v1.0.2 |

---

## Установка

### 1. RBAC манифест

```bash
sudo curl -o /var/lib/rancher/k3s/server/manifests/kube-vip-rbac.yaml \
    https://kube-vip.io/manifests/rbac.yaml
```

**Разбор:**

| Элемент | Объяснение |
|---------|------------|
| `curl -o <file>` | Скачать и сохранить в файл |
| `/var/lib/rancher/k3s/server/manifests/` | Директория auto-deploy K3s |
| `rbac.yaml` | Role-Based Access Control |

**RBAC** — система разрешений в Kubernetes:
- **ServiceAccount** — идентификация для подов
- **ClusterRole** — набор разрешений
- **ClusterRoleBinding** — связь роли с ServiceAccount

kube-vip нужны права для:
- Чтения нод
- Создания/обновления Leases (для выборов)
- Обновления Services (для LoadBalancer)

### 2. DaemonSet манифест

```bash
export VIP=192.168.20.225
export INTERFACE=enp1s0
export KVVERSION=v1.0.2
```

**export** — создать переменную окружения (доступна в подпроцессах).

```bash
# Скачать образ
sudo ctr image pull ghcr.io/kube-vip/kube-vip:$KVVERSION
```

**Разбор:**

| Элемент | Объяснение |
|---------|------------|
| `ctr` | CLI для containerd (низкоуровневый) |
| `image pull` | Скачать образ |
| `ghcr.io` | GitHub Container Registry |
| `$KVVERSION` | Подстановка переменной |

```bash
# Сгенерировать манифест
sudo ctr run --rm --net-host ghcr.io/kube-vip/kube-vip:$KVVERSION vip \
    /kube-vip manifest daemonset \
    --interface $INTERFACE \
    --address $VIP \
    --inCluster \
    --taint \
    --controlplane \
    --arp \
    --leaderElection | sudo tee /var/lib/rancher/k3s/server/manifests/kube-vip-daemonset.yaml
```

**Разбор ctr run:**

| Флаг | Объяснение |
|------|------------|
| `--rm` | Удалить контейнер после завершения |
| `--net-host` | Использовать сеть хоста (нужно для ARP) |
| `vip` | Имя контейнера |
| `/kube-vip manifest daemonset` | Команда внутри контейнера |

**Разбор флагов kube-vip:**

| Флаг | Объяснение |
|------|------------|
| `--interface $INTERFACE` | Сетевой интерфейс для VIP |
| `--address $VIP` | IP адрес VIP |
| `--inCluster` | Использовать in-cluster Kubernetes config |
| `--taint` | Запускать только на control-plane нодах |
| `--controlplane` | Режим control plane (VIP для API server) |
| `--arp` | Использовать ARP для failover |
| `--leaderElection` | Включить выборы лидера через Lease |

**Что делает `tee`:**
Записывает stdin в файл И выводит в stdout. С `sudo` — записывает с правами root.

### 3. Проверка

```bash
# Pod должен быть Running на каждой control-plane ноде
kubectl get pods -n kube-system -l app.kubernetes.io/name=kube-vip-ds -o wide
```

```bash
# VIP на интерфейсе (только на лидере!)
ip a show enp1s0 | grep 192.168.20.225
```

**`ip a show`** — показать IP адреса на интерфейсе.

Ожидаемый вывод на лидере:
```
inet 192.168.20.225/32 scope global enp1s0
```

`/32` — маска для одного IP (VIP не подсеть, а конкретный адрес).

---

## Как работает

### Последовательность запуска

1. K3s создаёт DaemonSet из манифеста
2. kube-vip запускается на каждой control-plane ноде
3. Ноды участвуют в выборах через Lease
4. Лидер добавляет VIP на интерфейс
5. Лидер отвечает на ARP для VIP

### При failover

1. Лидер перестаёт обновлять Lease
2. Другие ноды видят expired Lease
3. Новые выборы, новый лидер
4. Новый лидер добавляет VIP
5. Gratuitous ARP обновляет сеть
6. ~2-5 секунд downtime

### Диагностика

```bash
# Логи kube-vip
kubectl logs -n kube-system -l app.kubernetes.io/name=kube-vip-ds

# Кто сейчас лидер
kubectl -n kube-system get lease kube-vip-cp -o yaml
```

**Lease** содержит:
- `holderIdentity` — имя текущего лидера
- `leaseDurationSeconds` — как долго lease действителен
- `renewTime` — когда последний раз обновлён

---

## Альтернативные режимы

### BGP вместо ARP

Для крупных сетей с роутерами:

```bash
/kube-vip manifest daemonset \
    --interface $INTERFACE \
    --address $VIP \
    --inCluster \
    --taint \
    --controlplane \
    --bgp \
    --localAS 65000 \
    --bgpRouterID 192.168.20.221 \
    --bgppeers 192.168.20.1:65000::false,192.168.20.2:65000::false
```

**BGP (Border Gateway Protocol)** — протокол маршрутизации. Объявляет VIP роутерам, которые знают как достучаться.

### LoadBalancer Services

kube-vip может также обеспечивать LoadBalancer для Services (замена MetalLB):

```bash
--services \
--servicesElection
```

---

## Troubleshooting

### VIP не появляется на интерфейсе

1. **Проверить логи:**
```bash
kubectl logs -n kube-system -l app.kubernetes.io/name=kube-vip-ds
```

2. **Проверить Lease:**
```bash
kubectl -n kube-system get lease
```

3. **Проверить что интерфейс правильный:**
```bash
ip link show
```

### Два лидера (split-brain)

**Симптом:** VIP на нескольких нодах.

**Причина:** Сетевые проблемы между нодами.

**Решение:**
1. Проверить связность между нодами
2. Проверить firewall (etcd порты 2379-2380)
3. Перезапустить kube-vip поды

### API server недоступен по VIP

```bash
# Проверить что VIP отвечает
ping 192.168.20.225

# Проверить API server
curl -k https://192.168.20.225:6443/version
```

Если ping работает, но API нет — проблема в K3s, не в kube-vip.

---

## Ресурсы

- [kube-vip для K3s](https://kube-vip.io/docs/usage/k3s/)
- [kube-vip Architecture](https://kube-vip.io/docs/about/architecture/)
- [GitHub](https://github.com/kube-vip/kube-vip)

## См. также

- [[K3s]]
- [[K3s - Архитектура]]
- [[K3s - Установка HA]]
- [[Networking]]

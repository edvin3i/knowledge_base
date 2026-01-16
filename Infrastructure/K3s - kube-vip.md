---
tags:
  - k3s
  - networking
  - ha
created: 2025-01-15
---

# kube-vip

Virtual IP для отказоустойчивого доступа к [[K3s]] API Server.

## Зачем

Без VIP при падении master-ноды клиенты теряют доступ к API. kube-vip создаёт плавающий IP, который автоматически переезжает на живую ноду.

## Моя конфигурация

- **VIP:** `192.168.20.225`
- **Interface:** `enp1s0`
- **Mode:** ARP + Leader Election

## Установка

### 1. RBAC манифест

```bash
sudo curl -o /var/lib/rancher/k3s/server/manifests/kube-vip-rbac.yaml \
    https://kube-vip.io/manifests/rbac.yaml
```

### 2. DaemonSet манифест

```bash
export VIP=192.168.20.225
export INTERFACE=enp1s0
export KVVERSION=v1.0.2

# Скачать образ
sudo ctr image pull ghcr.io/kube-vip/kube-vip:$KVVERSION

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

### 3. Проверка

```bash
# Pod должен быть Running
kubectl get pods -n kube-system | grep kube-vip

# VIP на интерфейсе
ip a show enp1s0 | grep 192.168.20.225
```

## Как работает

1. kube-vip DaemonSet запускается на каждой control-plane ноде
2. Ноды участвуют в выборах лидера
3. Лидер добавляет VIP на свой интерфейс
4. При падении лидера — новые выборы, VIP переезжает

## Ресурсы

- [kube-vip для K3s](https://kube-vip.io/docs/usage/k3s/)
- [GitHub](https://github.com/kube-vip/kube-vip)

## См. также

- [[K3s]]
- [[K3s - Архитектура]]
- [[K3s - Установка HA]]

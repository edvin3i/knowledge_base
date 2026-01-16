---
tags:
  - k3s
  - howto
  - ha
  - debian
created: 2025-01-15
---

# K3s — Установка HA кластера

Пошаговая инструкция по развёртыванию [[K3s]] HA кластера на [[Debian]] 13.

## Подготовка системы

### Базовые утилиты

```bash
sudo apt install vim htop btop mc curl wget -y
```

### Настройка sudo

```bash
su -
apt update && apt install sudo
/usr/sbin/usermod -aG sudo nodeadm
```

> **Важно:** На минимальных Debian `/usr/sbin/` не в PATH — используй полный путь.

### Статические IP

> **Критично:** Для HA с etcd нужны статические IP. При смене IP кластер развалится.

Редактируем `/etc/network/interfaces`:

```
auto enp1s0
iface enp1s0 inet static
    address 192.168.20.221
    netmask 255.255.255.0
    gateway 192.168.20.254
    dns-nameservers 1.1.1.3 1.0.0.3
```

```bash
sudo systemctl restart networking
```

### Установка зависимостей

На **всех нодах**:

```bash
sudo apt update && sudo apt install -y iptables curl
```

---

## Установка кластера

### Node 1 — инициализация

Сгенерировать токен:
```bash
openssl rand -base64 32
```

Установить K3s:
```bash
curl -sfL https://get.k3s.io | K3S_TOKEN=<YOUR_TOKEN> sh -s - server \
    --cluster-init \
    --tls-san 192.168.20.225 \
    --disable servicelb \
    --write-kubeconfig-mode 644
```

**Флаги:**
- `--cluster-init` — инициализация HA с embedded etcd
- `--tls-san` — добавить VIP в сертификат
- `--disable servicelb` — отключить встроенный LB (используем [[kube-vip]])

### Настройка kube-vip

См. [[K3s - kube-vip]]

### Node 2 и Node 3

```bash
curl -sfL https://get.k3s.io | K3S_TOKEN=<YOUR_TOKEN> sh -s - server \
    --server https://192.168.20.225:6443 \
    --tls-san 192.168.20.225 \
    --disable servicelb \
    --write-kubeconfig-mode 644
```

> Используем VIP (`192.168.20.225`), не IP первой ноды.

---

## Проверка

```bash
# Все ноды Ready
kubectl get nodes

# Системные поды Running
kubectl get pods -n kube-system

# kube-vip на каждой ноде
kubectl get pods -n kube-system -l app.kubernetes.io/name=kube-vip-ds
```

**Тест отказоустойчивости:**
```bash
sudo reboot  # на любой ноде
# С другой ноды кластер должен работать
kubectl get nodes
```

---

## Добавление worker нод

Для дополнительных нод (GPU, edge):

```bash
curl -sfL https://get.k3s.io | K3S_URL=https://192.168.20.225:6443 \
    K3S_TOKEN=<YOUR_TOKEN> sh -
```

Labels:
```bash
kubectl label nodes <gpu-node> node-type=gpu
kubectl label nodes <jetson-node> node-type=edge-ai
```

---

## Удаление K3s

```bash
# Server
/usr/local/bin/k3s-uninstall.sh

# Agent
/usr/local/bin/k3s-agent-uninstall.sh
```

## См. также

- [[K3s]]
- [[K3s - Архитектура]]
- [[K3s - kube-vip]]
- [[K3s - Troubleshooting]]

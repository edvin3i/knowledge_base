---
tags:
  - hardware
  - homelab
  - k3s
  - gpu
created: 2026-01-19
---

# polydev-desktop

GPU нода [[K3s]] кластера. Рабочая станция для ML/AI задач.

## Конфигурация

| Параметр | Значение |
|----------|----------|
| **IP** | 192.168.20.16 |
| **OS** | Ubuntu 22.04.5 LTS |
| **Kernel** | 6.8.0-87-generic |
| **Роль** | K3s Agent (GPU worker) |

### CPU

| Параметр | Значение |
|----------|----------|
| **Ядра** | 24 |
| **Allocatable** | 24 |

### RAM

| Параметр | Значение |
|----------|----------|
| **Всего** | ~64 GB |
| **Allocatable** | 65666352Ki (~62 GB) |

### GPU

| Параметр | Значение |
|----------|----------|
| **Модель** | NVIDIA RTX A6000 |
| **VRAM** | 48 GB (49140 MiB) |
| **Driver** | 555.52.04 |
| **CUDA** | 12.5 |

### Storage

| Параметр | Значение | Назначение |
|----------|----------|------------|
| **Root disk** | ~434 GB | OS, `/var/lib/longhorn` |
| **Data disk** | /mnt | [[Longhorn]] storage (`/mnt/longhorn`) |

**Longhorn диски на этой ноде:**
- `/var/lib/longhorn` — default disk
- `/mnt/longhorn` — дополнительный большой диск

## Роль в кластере

- Worker нода (только Agent, не участвует в control plane)
- GPU workloads через `nvidia.com/gpu` resource
- RuntimeClass `nvidia` для контейнеров с GPU
- [[CVAT]] Nuclio AI функции для автоматической аннотации

## ML Workloads

### CVAT Nuclio Functions

На этой ноде запускаются GPU-ускоренные AI модели для [[CVAT]]:

| Функция | Модель | VRAM |
|---------|--------|------|
| `yolo11x-cvat-detector-gpu` | YOLOv11x (custom) | ~4GB |

**Деплой функции:**

```bash
nuctl deploy --project-name cvat \
  --path /path/to/serverless/custom/nuclio \
  --namespace cvat \
  --platform kube \
  --registry docker.io/edvin3i
```

### DiskPressure при деплое GPU функций

**Проблема:** PyTorch CUDA образы очень большие (~8-12GB). При скачивании нескольких образов диск переполняется.

**Симптомы:**
- Pod статус `Evicted`
- Events: `The node was low on resource: ephemeral-storage`
- Node condition: `DiskPressure=True`

**Диагностика:**

```bash
# Проверить состояние ноды
kubectl describe node polydev-desktop | grep -A5 "Conditions:"

# На ноде: проверить место
df -h /var/lib/containerd
```

**Решение:**

```bash
# На polydev-desktop:
sudo crictl rmi --prune

# Проверить что DiskPressure снялся
kubectl describe node polydev-desktop | grep DiskPressure
```

**Профилактика:**
- Использовать runtime образы вместо devel (меньше размер)
- Периодически чистить неиспользуемые образы
- Настроить garbage collection в kubelet

## Kubernetes Labels

```bash
kubectl label nodes polydev-desktop node-role.kubernetes.io/gpu=true
```

## Проверка GPU в кластере

```bash
# Статус GPU
nvidia-smi

# GPU ресурсы в K8s
kubectl get nodes polydev-desktop -o jsonpath='{.status.allocatable.nvidia\.com/gpu}'
```

## UFW Firewall

### Теория: Что такое UFW

**UFW (Uncomplicated Firewall)** — frontend для iptables в Ubuntu. Управляет сетевыми правилами: какой трафик разрешён, какой заблокирован.

```
┌─────────────────────────────────────────────────────────────┐
│                    Как работает firewall                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   Входящий пакет                                            │
│        │                                                     │
│        ▼                                                     │
│   ┌─────────┐     match?     ┌─────────┐                    │
│   │ Rule 1  │ ──────────────► │ ALLOW   │                    │
│   └─────────┘       no       └─────────┘                    │
│        │                                                     │
│        ▼                                                     │
│   ┌─────────┐     match?     ┌─────────┐                    │
│   │ Rule 2  │ ──────────────► │ DENY    │                    │
│   └─────────┘       no       └─────────┘                    │
│        │                                                     │
│        ▼                                                     │
│   ┌─────────────────┐                                        │
│   │ Default Policy  │  (обычно DENY для INPUT)              │
│   └─────────────────┘                                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Почему K3s требует настройки firewall

Kubernetes использует несколько сетей:
1. **Физическая сеть** (192.168.20.0/24) — ноды общаются друг с другом
2. **Pod сеть** (10.42.0.0/16) — IP адреса контейнеров
3. **Service сеть** (10.43.0.0/16) — виртуальные IP сервисов

UFW по умолчанию блокирует входящий трафик с незнакомых сетей (10.42.x.x, 10.43.x.x).

### Необходимые правила

```bash
# K3s API — для kubectl и других нод
sudo ufw allow 6443/tcp
```

| Параметр | Значение |
|----------|----------|
| `6443` | Порт Kubernetes API server |
| `tcp` | Протокол |

```bash
# Kubelet — API для управления контейнерами
sudo ufw allow 10250/tcp
```

**Kubelet** слушает на 10250. Используется для:
- Получения логов (`kubectl logs`)
- Exec в контейнер (`kubectl exec`)
- Port-forward

```bash
# Flannel VXLAN — overlay сеть
sudo ufw allow 8472/udp
```

**VXLAN** (Virtual Extensible LAN) — туннелирование для pod сети. Поды на разных нодах общаются через этот туннель.

```bash
# Pod network (Flannel CNI)
sudo ufw allow from 10.42.0.0/16
```

Разрешить трафик **от** подов. Без этого:
- Поды не могут инициировать соединения к этой ноде
- Admission webhooks не работают (например Longhorn)

```bash
# Service network
sudo ufw allow from 10.43.0.0/16
```

Трафик от ClusterIP сервисов. kube-proxy транслирует Service IP в Pod IP.

```bash
# Другие ноды кластера
sudo ufw allow from 192.168.20.221
sudo ufw allow from 192.168.20.222
sudo ufw allow from 192.168.20.223
```

Полный доступ для control-plane нод. Нужен для:
- etcd синхронизации (2379-2380)
- Scheduling
- Health checks

### Базовые команды UFW

```bash
# Включить firewall
sudo ufw enable

# Выключить
sudo ufw disable

# Статус и правила
sudo ufw status
sudo ufw status numbered  # с номерами для удаления

# Добавить правило
sudo ufw allow 80/tcp
sudo ufw allow from 10.0.0.0/8

# Удалить правило
sudo ufw delete 5         # по номеру
sudo ufw delete allow 80  # по описанию

# Сбросить все правила
sudo ufw reset
```

**Разбор синтаксиса:**

| Команда | Значение |
|---------|----------|
| `allow` | Разрешить |
| `deny` | Запретить |
| `80/tcp` | Порт/протокол |
| `from 10.0.0.0/8` | Источник (CIDR) |
| `to any port 80` | Назначение |

### Проверка

```bash
sudo ufw status numbered
```

Ожидаемый вывод:
```
Status: active

     To                         Action      From
     --                         ------      ----
[ 1] 6443/tcp                   ALLOW IN    Anywhere
[ 2] 10250/tcp                  ALLOW IN    Anywhere
[ 3] 8472/udp                   ALLOW IN    Anywhere
[ 4] Anywhere                   ALLOW IN    10.42.0.0/16
[ 5] Anywhere                   ALLOW IN    10.43.0.0/16
...
```

### Диагностика проблем

```bash
# Логи firewall
sudo tail -f /var/log/ufw.log

# Проверить что пакеты доходят
sudo tcpdump -i any port 10250

# Временно отключить (для теста)
sudo ufw disable
```

**Важно:** Без этих правил Longhorn и другие компоненты не смогут общаться между подами. См. [[K3s - Troubleshooting#UFW блокирует pod-to-pod трафик]].

## GPU Sharing

RTX A6000 **не поддерживает MIG** (Multi-Instance GPU), но поддерживает:

- **Time-Slicing** — переключение контекста между подами
- **MPS** — параллельное выполнение CUDA процессов

Рекомендуется **Time-Slicing** с `replicas: 4` для разделения 48 GB VRAM между:
- YOLO (Nuclio) ~4-6 GB
- RIFE ~6-8 GB
- Real-ESRGAN ~4-6 GB
- Резерв

Подробнее: [[K3s - GPU Sharing]]

## См. также

- [[K3s]]
- [[K3s - GPU Support]]
- [[K3s - GPU Sharing]]
- [[K3s - Troubleshooting]]
- [[CVAT]]
- [[Longhorn]]
- [[polynode-1]]
- [[polynode-2]]
- [[polynode-3]]

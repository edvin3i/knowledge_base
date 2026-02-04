---
tags:
  - k3s
  - troubleshooting
created: 2025-01-15
---

# K3s — Troubleshooting

Решение проблем с [[K3s]] кластером.

## usermod: command not found

**Причина:** `/usr/sbin/` не в PATH на минимальных [[Debian]].

**Решение:**
```bash
/usr/sbin/usermod -aG sudo nodeadm
# или
adduser nodeadm sudo
```

## Нода не присоединяется к кластеру

**Проверить:**
1. Токен правильный
2. Сеть между нодами (ping)
3. Порты открыты (6443, 2379, 2380)

```bash
# На новой ноде
curl -k https://192.168.20.225:6443
```

## etcd: no leader

**Причина:** Нет кворума (менее 2 нод из 3).

**Решение:** Поднять хотя бы 2 ноды.

## kube-vip не стартует

**Проверить:**
```bash
kubectl logs -n kube-system -l app.kubernetes.io/name=kube-vip-ds
```

**Частые причины:**
- Неверный интерфейс в манифесте
- VIP уже занят

## DNS не резолвится внутри подов

```bash
kubectl run -it --rm debug --image=busybox -- nslookup kubernetes
```

**Решение:** Проверить CoreDNS:
```bash
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system -l k8s-app=kube-dns
```

## Полезные команды диагностики

```bash
# Статус нод
kubectl get nodes -o wide

# Системные поды
kubectl get pods -n kube-system

# Логи K3s
journalctl -u k3s -f

# etcd членство
kubectl get endpoints -n kube-system
```

## UFW блокирует pod-to-pod трафик

**Симптом:** Поды застревают в `CrashLoopBackOff` или `ContainerCreating`. В логах таймауты при обращении к другим сервисам.

**Пример:** `longhorn-manager` не может достучаться до admission webhook.

**Причина:** UFW (Ubuntu Firewall) по умолчанию блокирует трафик между подами K3s.

**Решение:** Открыть порты для K3s сетей:

```bash
# Pod network (Flannel CNI default)
sudo ufw allow from 10.42.0.0/16

# Service network (ClusterIP)
sudo ufw allow from 10.43.0.0/16

# Kubelet API
sudo ufw allow 10250/tcp

# Flannel VXLAN overlay
sudo ufw allow 8472/udp

# Ноды кластера (если нужно)
sudo ufw allow from 192.168.20.0/24
```

**Проверка:**
```bash
sudo ufw status numbered
```

**Важно:** На [[Debian]] минимальной установке UFW обычно не установлен. Проблема актуальна для Ubuntu (например, [[polydev-desktop]]).

## Longhorn pods не стартуют

**Симптом:** `longhorn-manager` в `CrashLoopBackOff` на отдельных нодах.

**Проверка:**
```bash
kubectl -n longhorn-system logs -l app=longhorn-manager --all-containers
kubectl -n longhorn-system get pods -o wide
```

**Возможные причины:**
1. **UFW/Firewall** — см. выше
2. **iscsid не запущен** — `sudo systemctl enable --now iscsid`
3. **Нет open-iscsi** — `sudo apt install open-iscsi`

## NVIDIA Device Plugin не видит GPU

**Симптом:** `nvidia.com/gpu: 0` в allocatable ресурсах ноды.

**Проверка:**
```bash
kubectl logs -n kube-system -l app.kubernetes.io/name=nvidia-device-plugin-ds
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}: {.status.allocatable.nvidia\.com/gpu}{"\n"}{end}'
```

**Решение:** Device plugin должен работать с nvidia runtime:

```bash
kubectl -n kube-system patch daemonset nvidia-device-plugin-daemonset \
  --type='json' \
  -p='[{"op": "add", "path": "/spec/template/spec/runtimeClassName", "value": "nvidia"}]'
```

## См. также

- [[K3s]]
- [[K3s - Установка HA]]
- [[K3s - GPU Support]]
- [[Longhorn]]
- [[polydev-desktop]]

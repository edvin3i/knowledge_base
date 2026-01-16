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

## См. также

- [[K3s]]
- [[K3s - Установка HA]]

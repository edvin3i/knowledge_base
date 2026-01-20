---
tags:
  - hardware
  - homelab
  - k3s
created: 2025-01-15
---

# polynode-1

Первая нода [[K3s]] кластера.

## Конфигурация

| Параметр | Значение |
|----------|----------|
| **Железо** | [[Dell OptiPlex 3050]] |
| **IP** | 192.168.20.221 |
| **OS** | [[Debian]] 13 |
| **Роль** | K3s Server + Agent + etcd |

## Роль в кластере

- Инициализация кластера (`--cluster-init`)
- Один из 3 серверов etcd (кворум)
- Участвует в выборах [[K3s - kube-vip|kube-vip]] лидера

## См. также

- [[K3s]]
- [[Longhorn]]
- [[polynode-2]]
- [[polynode-3]]
- [[polydev-desktop]]

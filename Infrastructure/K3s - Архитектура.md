---
tags:
  - k3s
  - architecture
  - homelab
created: 2025-01-15
updated: 2026-01-19
---

# K3s — Архитектура кластера

Схема моего HA кластера [[K3s]].

## Топология

```
                    ┌─────────────────────────────┐
                    │      Virtual IP (VIP)       │
                    │      192.168.20.225         │
                    │    управляется kube-vip     │
                    └─────────────┬───────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
        ▼                         ▼                         ▼
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│   polynode-1  │       │   polynode-2  │       │   polynode-3  │
│192.168.20.221 │       │192.168.20.222 │       │192.168.20.223 │
│───────────────│       │───────────────│       │───────────────│
│ K3s Server    │◄─────►│ K3s Server    │◄─────►│ K3s Server    │
│ + Agent       │ etcd  │ + Agent       │ etcd  │ + Agent       │
│ + etcd        │ sync  │ + etcd        │ sync  │ + etcd        │
│ + kube-vip    │       │ + kube-vip    │       │ + kube-vip    │
└───────────────┘       └───────────────┘       └───────────────┘
        │                         │                         │
        └─────────────────────────┼─────────────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │      polydev-desktop        │
                    │      192.168.20.16          │
                    │─────────────────────────────│
                    │  K3s Agent (GPU Worker)     │
                    │  NVIDIA RTX A6000 (48GB)    │
                    │  24 CPU | 64GB RAM          │
                    └─────────────────────────────┘
```

### Control Plane (Servers)

**Железо:** [[Dell OptiPlex 3050]] | Intel Core i5-7500T | RAM 8GB | SSD 256GB

### GPU Worker

**Железо:** [[polydev-desktop]] | 24 CPU cores | RAM 64GB | NVIDIA RTX A6000 48GB

## Компоненты

| Компонент | Описание |
|-----------|----------|
| **K3s Server** | Control plane: API Server, Controller Manager, Scheduler |
| **K3s Agent** | Worker: kubelet, kube-proxy |
| **Embedded etcd** | Распределённая БД состояния (кворум 2 из 3) |
| **[[K3s - kube-vip\|kube-vip]]** | Virtual IP для отказоустойчивого доступа к API |
| **[[Longhorn]]** | Distributed block storage (replicated across nodes) |
| **Flannel** | CNI plugin (VXLAN overlay network) |
| **Traefik** | Ingress controller (built-in) |

## Сети

| Сеть | CIDR | Назначение |
|------|------|------------|
| **Физическая** | `192.168.20.0/24` | LAN, ноды кластера |
| **Pod Network** | `10.42.0.0/16` | IP адреса подов (Flannel) |
| **Service Network** | `10.43.0.0/16` | ClusterIP сервисов |

## Требуемые порты

| Порт | Протокол | Назначение |
|------|----------|------------|
| 6443 | TCP | Kubernetes API server |
| 2379 | TCP | etcd client |
| 2380 | TCP | etcd peer |
| 10250 | TCP | Kubelet metrics |
| 8472 | UDP | Flannel VXLAN |

## Планируемое расширение

- [x] GPU нода (RTX A6000) — [[polydev-desktop]]
- [ ] Edge нода (Jetson Nano)

```
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
      ┌─────────────────────────┐     ┌───────────────┐
      │    polydev-desktop      │     │  Jetson Nano  │
      │      RTX A6000          │     │  Agent only   │
      │      ГОТОВО             │     │  label: edge  │
      └─────────────────────────┘     └───────────────┘
```

## См. также

- [[K3s]]
- [[K3s - Установка HA]]
- [[K3s - GPU Support]]
- [[K3s - kube-vip]]
- [[Longhorn]]

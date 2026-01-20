---
tags:
  - networking
  - infrastructure
created: 2026-01-19
---

# Networking

Сетевые заметки для [[Homelab]].

## Топология

- **Подсеть:** `192.168.20.0/24`
- **Gateway:** `192.168.20.254`
- **DNS:** Cloudflare Family (`1.1.1.3`)

## IP адреса

| Устройство | IP |
|------------|-----|
| Router/Gateway | 192.168.20.254 |
| [[Cisco Meraki MX64]] | TBD |
| [[polynode-1]] | 192.168.20.221 |
| [[polynode-2]] | 192.168.20.222 |
| [[polynode-3]] | 192.168.20.223 |
| [[polydev-desktop]] | 192.168.20.16 |
| K3s VIP | 192.168.20.225 |

## K3s Overlay Networks

Kubernetes использует виртуальные сети поверх физической:

| Сеть | CIDR | Назначение |
|------|------|------------|
| **Pod Network** | `10.42.0.0/16` | IP адреса всех подов (Flannel CNI) |
| **Service Network** | `10.43.0.0/16` | ClusterIP сервисов |

**Важно:** Эти сети должны быть разрешены в firewall. См. [[K3s - Troubleshooting#UFW блокирует pod-to-pod трафик]].

## Порты K3s

| Порт | Протокол | Назначение |
|------|----------|------------|
| 6443 | TCP | Kubernetes API |
| 2379-2380 | TCP | etcd |
| 10250 | TCP | Kubelet |
| 8472 | UDP | Flannel VXLAN |
| 9500 | TCP | Longhorn (instance-manager) |

## См. также

- [[Homelab]]
- [[K3s - Архитектура]]
- [[K3s - Troubleshooting]]
- [[Longhorn]]
- [[OpenWrt]]

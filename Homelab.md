---
tags:
  - homelab
  - infrastructure
  - moc
created: 2025-01-15
---

# Homelab

Моя домашняя инфраструктура.

## Сеть

**Подсеть:** `192.168.20.0/24`
**Gateway:** `192.168.20.254`
**DNS:** Cloudflare Family (`1.1.1.3`)

## Оборудование

### Compute

| Устройство | IP | Роль |
|------------|-----|------|
| [[polynode-1]] | 192.168.20.221 | [[K3s]] server |
| [[polynode-2]] | 192.168.20.222 | [[K3s]] server |
| [[polynode-3]] | 192.168.20.223 | [[K3s]] server |

### Networking

| Устройство | IP | Роль |
|------------|-----|------|
| [[Cisco Meraki MX64]] | 192.168.20.222 | Managed switch |
| Router | 192.168.20.254 | Gateway, DHCP |

## Кластер K3s

- **VIP:** `192.168.20.225`
- **Конфигурация:** HA с embedded etcd
- **Подробнее:** [[K3s]]

## Планы

- [ ] GPU нода (RTX A6000)
- [ ] Edge нода (Jetson Nano)
- [ ] Мониторинг (Prometheus + Grafana)
- [ ] Storage (Longhorn / NFS)

## Диаграмма

```
Internet
    │
    ▼
┌─────────────────┐
│  Router         │
│  192.168.20.254 │
└────────┬────────┘
         │
    ┌────┴────┐
    │  Switch │  ← MX64 (192.168.20.222)
    │         │
    └┬───┬───┬┘
     │   │   │
     ▼   ▼   ▼
  ┌───┐┌───┐┌───┐
  │ 1 ││ 2 ││ 3 │  ← polynode-1/2/3
  └───┘└───┘└───┘
     K3s HA Cluster
     VIP: 192.168.20.225
```

## Документация

- [[K3s]] — кластер
- [[OpenWrt]] — прошивка свитча
- [[Networking]] — сетевые заметки

## См. также

- [[Home]]

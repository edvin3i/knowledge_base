---
tags:
  - homelab
  - infrastructure
  - moc
created: 2025-01-15
updated: 2026-02-14
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
| [[polydev-desktop]] | 192.168.20.16 | [[K3s]] agent (GPU) |

### Networking

| Устройство | IP | Роль |
|------------|-----|------|
| [[Cisco Meraki MX64]] | 192.168.20.220 | Managed switch |
| Router | 192.168.20.254 | Gateway, DHCP |

## Кластер K3s

- **VIP:** `192.168.20.225`
- **Ingress IP:** `192.168.20.235` ([[MetalLB]])
- **Конфигурация:** HA с embedded etcd (3 server + 1 GPU worker)
- **GPU:** RTX A6000 на [[polydev-desktop]]
- **Подробнее:** [[K3s]]

## Планы

- [x] GPU нода (RTX A6000) — [[polydev-desktop]]
- [x] Storage — [[Longhorn]] v1.10.1
- [x] [[CVAT]] v2.39.0 для аннотации данных
- [x] [[MinIO]] — S3-совместимое хранилище
- [x] [[ClearML]] — MLOps платформа
- [ ] Edge нода (Jetson Nano)
- [ ] Мониторинг (Prometheus + Grafana)

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
    │  Switch │  ← MX64
    │         │
    └┬───┬───┬───┬┘
     │   │   │   │
     ▼   ▼   ▼   ▼
  ┌───┐┌───┐┌───┐┌─────────────┐
  │ 1 ││ 2 ││ 3 ││ polydev     │  ← GPU Node
  └───┘└───┘└───┘│ RTX A6000   │
   polynode-1/2/3└─────────────┘

     K3s HA Cluster
     VIP: 192.168.20.225
```

## Документация

### K3s Кластер (Homelab)

- [[K3s]] — кластер
- [[MetalLB]] — LoadBalancer для bare-metal
- [[Longhorn]] — distributed block storage
- [[MinIO]] — S3 object storage
- [[CVAT]] — аннотация данных
- [[ClearML]] — MLOps платформа
- [[OpenWrt]] — прошивка свитча
- [[Networking]] — сетевые заметки

### VPS Hetzner

- [[Outline]] — база знаний (kb.aura.ibondar.pro)

## См. также

- [[Home]]

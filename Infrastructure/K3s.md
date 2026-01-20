---
tags:
  - kubernetes
  - infrastructure
  - homelab
  - ha
created: 2025-01-15
updated: 2026-01-20
---

# K3s

Легковесный Kubernetes от Rancher. Мой основной кластер для [[Homelab]].

## Мой кластер

**Конфигурация:** HA с embedded etcd (3 server ноды)

| Нода | IP | Роль | Железо |
|------|----|------|--------|
| [[polynode-1]] | 192.168.20.221 | Server + Agent + etcd | [[Dell OptiPlex 3050]] |
| [[polynode-2]] | 192.168.20.222 | Server + Agent + etcd | [[Dell OptiPlex 3050]] |
| [[polynode-3]] | 192.168.20.223 | Server + Agent + etcd | [[Dell OptiPlex 3050]] |
| [[polydev-desktop]] | 192.168.20.16 | Agent (GPU) | Custom Workstation |

**VIP:** `192.168.20.225` (управляется [[K3s - kube-vip|kube-vip]])

## Документация

- [[K3s - Архитектура]] — схема кластера, порты, компоненты
- [[K3s - Установка HA]] — пошаговая инструкция
- [[K3s - kube-vip]] — настройка Virtual IP для API
- [[K3s - GPU Support]] — настройка GPU нод с NVIDIA
- [[K3s - Troubleshooting]] — решение проблем

## Networking

| Компонент | Назначение | IP |
|-----------|------------|-----|
| **kube-vip** | VIP для Kubernetes API | 192.168.20.225 |
| **[[MetalLB]]** | LoadBalancer для сервисов | 192.168.20.235-245 |
| **Traefik** | Ingress Controller | 192.168.20.235 |

K3s включает Traefik по умолчанию, но ему нужен [[MetalLB]] для получения внешнего IP на bare-metal.

## Планы расширения

- [x] GPU нода с RTX A6000 ([[polydev-desktop]])
- [ ] Edge нода Jetson Nano

## Storage

**Основной:** [[Longhorn]] v1.10.1 (distributed block storage)
**Legacy:** `local-path` (K3s default, отключён как default)

```bash
# Проверка StorageClass
kubectl get storageclass

# Статус Longhorn
kubectl -n longhorn-system get pods
kubectl -n longhorn-system get nodes.longhorn.io
```

## Workloads

| Приложение | Namespace | Назначение |
|------------|-----------|------------|
| [[CVAT]] | `cvat` | Аннотация данных для ML |
| [[MinIO]] | `minio` | S3 object storage |
| [[ClearML]] | `clearml` | MLOps платформа |

- [[Deployments]]
- [[Services]]
- [[Ingress]]

## Инструменты

- [[kubectl]] — CLI управления
- [[Helm]] — пакетный менеджер
- [[Lens]] — GUI для кластера
- [[Longhorn]] — storage management UI
- [[MetalLB]] — LoadBalancer для bare-metal

## Ресурсы

- [K3s Documentation](https://docs.k3s.io/)
- [K3s Quick Start](https://docs.k3s.io/quick-start)
- [kube-vip для K3s](https://kube-vip.io/docs/usage/k3s/)
- [[Kubernetes]] — общие концепции

## См. также

- [[Homelab]]
- [[Debian]]

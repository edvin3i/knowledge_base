---
tags:
  - kubernetes
  - infrastructure
  - homelab
  - ha
created: 2025-01-15
updated: 2025-01-16
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

**VIP:** `192.168.20.225` (управляется [[kube-vip]])

## Документация

- [[K3s - Архитектура]] — схема кластера, порты, компоненты
- [[K3s - Установка HA]] — пошаговая инструкция
- [[K3s - kube-vip]] — настройка Virtual IP
- [[K3s - Troubleshooting]] — решение проблем

## Планы расширения

- [ ] GPU нода с RTX A6000
- [ ] Edge нода Jetson Nano

## Workloads

- [[Deployments]]
- [[Services]]
- [[Ingress]]

## Инструменты

- [[kubectl]] — CLI управления
- [[Helm]] — пакетный менеджер
- [[Lens]] — GUI для кластера

## Ресурсы

- [K3s Documentation](https://docs.k3s.io/)
- [K3s Quick Start](https://docs.k3s.io/quick-start)
- [kube-vip для K3s](https://kube-vip.io/docs/usage/k3s/)
- [[Kubernetes]] — общие концепции

## См. также

- [[Homelab]]
- [[Debian]]

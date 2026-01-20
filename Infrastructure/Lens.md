---
tags:
  - kubernetes
  - tools
  - gui
created: 2026-01-19
---

# Lens

GUI для управления Kubernetes кластерами.

## Установка

Скачать с [k8slens.dev](https://k8slens.dev/)

Или через snap:
```bash
sudo snap install kontena-lens --classic
```

## Возможности

- Визуализация кластера
- Управление ресурсами (pods, deployments, services)
- Встроенный терминал
- Мониторинг метрик
- Управление несколькими кластерами

## Настройка

1. Добавить kubeconfig файл
2. Для K3s: скопировать `/etc/rancher/k3s/k3s.yaml` и заменить `127.0.0.1` на VIP

## См. также

- [[Kubernetes]]
- [[K3s]]
- [[kubectl]]

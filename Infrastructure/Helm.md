---
tags:
  - kubernetes
  - tools
created: 2026-01-19
---

# Helm

Пакетный менеджер для Kubernetes.

## Установка

```bash
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

## Основные команды

```bash
# Поиск чартов
helm search repo <name>

# Установка
helm install <release> <chart>

# Список релизов
helm list

# Удаление
helm uninstall <release>
```

## Репозитории

```bash
# Добавить репозиторий
helm repo add bitnami https://charts.bitnami.com/bitnami

# Обновить
helm repo update
```

## См. также

- [[Kubernetes]]
- [[K3s]]
- [[kubectl]]

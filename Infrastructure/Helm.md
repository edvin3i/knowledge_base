---
tags:
  - kubernetes
  - tools
created: 2026-01-19
---

# Helm

Пакетный менеджер для Kubernetes.

## Теория: Что такое Helm

### Проблема

Типичное приложение в Kubernetes — это 5-20 YAML файлов (Deployment, Service, ConfigMap, Secret, PVC, ...). Управлять ими вручную:
- Сложно устанавливать (20 `kubectl apply`)
- Сложно обновлять (какие файлы изменились?)
- Сложно удалять (какие ресурсы создал это приложение?)
- Нет параметризации (hardcoded значения в YAML)

### Решение: Helm

**Helm** — как `apt`/`pip`, но для Kubernetes:

| Концепция | Аналогия | Описание |
|-----------|----------|----------|
| **Chart** | `.deb` / `.rpm` пакет | Набор шаблонов YAML + метаданные |
| **Release** | Установленный пакет | Конкретная установка chart в кластере |
| **Values** | Конфиг-файл | Параметры для кастомизации chart |
| **Repository** | APT/pip репозиторий | Хранилище chart'ов |

```
┌─────────────────────────────────────────────────────────────┐
│                    Как работает Helm                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   values.yaml          Chart (templates/)                    │
│   ┌──────────┐        ┌───────────────────┐                 │
│   │ replicas:│        │ deployment.yaml   │                 │
│   │   3      │───────►│ service.yaml      │──► kubectl      │
│   │ image:   │ render │ configmap.yaml    │    apply        │
│   │  nginx   │        │ pvc.yaml          │                 │
│   └──────────┘        └───────────────────┘                 │
│                                                              │
│   Helm берёт шаблоны (templates), подставляет значения      │
│   (values), и применяет готовые YAML в кластер.             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Ключевые команды

| Команда | Аналогия | Что делает |
|---------|----------|-----------|
| `helm install` | `apt install` | Установить chart как release |
| `helm upgrade` | `apt upgrade` | Обновить release (новые values или версия) |
| `helm uninstall` | `apt remove` | Удалить release и все его ресурсы |
| `helm list` | `dpkg -l` | Показать установленные releases |
| `helm repo add` | `add-apt-repository` | Добавить репозиторий chart'ов |

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

---
tags:
  - kubernetes
  - networking
created: 2026-01-19
---

# Services

Kubernetes Service — абстракция для доступа к группе подов.

## Типы

| Тип | Описание |
|-----|----------|
| `ClusterIP` | Внутренний IP (по умолчанию) |
| `NodePort` | Порт на каждой ноде (30000-32767) |
| `LoadBalancer` | Внешний балансировщик |
| `ExternalName` | DNS alias для внешнего сервиса |

## Примеры

```bash
# Создать NodePort сервис
kubectl expose deployment nginx --port=80 --type=NodePort

# Посмотреть сервисы
kubectl get svc
```

## См. также

- [[Kubernetes]]
- [[K3s]]
- [[Deployments]]
- [[Ingress]]

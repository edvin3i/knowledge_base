---
tags:
  - kubernetes
  - k3s
  - workloads
created: 2025-01-16
updated: 2025-01-16
---

# Deployments

Deployment — ресурс Kubernetes для декларативного управления подами.

## Быстрый тест кластера

### Создать deployment

```bash
kubectl create deployment nginx-test --image=nginx:alpine --replicas=3
```

### Создать сервис (NodePort)

```bash
kubectl expose deployment nginx-test --port=80 --type=NodePort
```

### Проверить

```bash
# Статус подов
kubectl get pods -l app=nginx-test

# Сервис и порт
kubectl get svc nginx-test
```

Пример вывода:
```
NAME         TYPE       CLUSTER-IP      EXTERNAL-IP   PORT(S)        AGE
nginx-test   NodePort   10.43.226.217   <none>        80:32667/TCP   95s
```

### Тест

```bash
# Через VIP
curl http://192.168.20.225:<NodePort>

# Через любую ноду
curl http://192.168.20.221:<NodePort>
```

### Удалить

```bash
kubectl delete deployment nginx-test
kubectl delete svc nginx-test
```

## Типы сервисов

| Тип | Описание |
|-----|----------|
| `ClusterIP` | Внутренний IP (по умолчанию) |
| `NodePort` | Порт на каждой ноде (30000-32767) |
| `LoadBalancer` | Внешний балансировщик |

## Управление deployment

```bash
# Масштабирование
kubectl scale deployment nginx-test --replicas=5

# Обновление образа
kubectl set image deployment/nginx-test nginx=nginx:latest

# История rollout
kubectl rollout history deployment/nginx-test

# Откат
kubectl rollout undo deployment/nginx-test
```

## См. также

- [[K3s]]
- [[kubectl]]
- [[Services]]
- [[Ingress]]

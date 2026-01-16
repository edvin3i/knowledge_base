---
tags:
  - kubernetes
  - infrastructure
  - containers
created: 2025-01-15
---

# Kubernetes

Оркестратор контейнеров.

## Основные концепции

### Объекты
- **Pod** — минимальная единица, один или несколько контейнеров
- **Deployment** — декларативное управление Pod'ами
- **Service** — сетевой эндпоинт для доступа к Pod'ам
- **Ingress** — HTTP/HTTPS роутинг снаружи
- **ConfigMap / Secret** — конфигурация
- **PersistentVolume** — хранилище

### Архитектура
- **Control Plane**: API Server, Scheduler, Controller Manager, etcd
- **Worker Nodes**: kubelet, kube-proxy, container runtime

## Дистрибутивы
- [[K3s]] — легковесный, для homelab
- [[K8s]] — полноценный
- [[MicroK8s]] — от Canonical
- [[Kind]] — для локальной разработки

## Команды kubectl
```bash
kubectl get pods -A           # все поды
kubectl describe pod <name>   # детали пода
kubectl logs <pod>            # логи
kubectl exec -it <pod> -- sh  # shell в контейнер
kubectl apply -f manifest.yaml
```

## Ресурсы
- [Документация](https://kubernetes.io/docs/)

---
tags:
  - kubernetes
  - infrastructure
  - containers
created: 2025-01-15
updated: 2026-01-24
---

# Kubernetes

Оркестратор контейнеров. Автоматизирует развёртывание, масштабирование и управление контейнеризированными приложениями.

## Содержание

- [[#Основные концепции]]
- [[#Архитектура]]
- [[#Документация по темам]]
- [[#Дистрибутивы]]
- [[#Команды kubectl]]

---

## Основные концепции

### Workloads (рабочие нагрузки)

| Объект | Описание |
|--------|----------|
| **Pod** | Минимальная единица. Один или несколько контейнеров с общим IP. [[VM_Container_Pod|Подробно: VM, Container, Pod]] |
| **Deployment** | Декларативное управление Pod'ами (rolling updates, replicas) |
| **StatefulSet** | Для stateful приложений (БД), сохраняет идентичность Pod'ов |
| **DaemonSet** | Запускает Pod на каждой ноде (мониторинг, логирование) |
| **Job / CronJob** | Разовые и периодические задачи |

### Networking (сеть)

| Объект | Описание |
|--------|----------|
| **Service** | Стабильный IP/DNS для группы Pod'ов. [[Services]] |
| **Ingress** | HTTP/HTTPS роутинг снаружи. [[Ingress]] |
| **NetworkPolicy** | Правила firewall между Pod'ами |

> Подробно: [[Kubernetes - Сеть и взаимодействие]]

### Configuration (конфигурация)

| Объект | Описание |
|--------|----------|
| **ConfigMap** | Конфигурация в виде key-value (не секреты) |
| **Secret** | Чувствительные данные (пароли, токены) |

### Storage (хранилище)

| Объект | Описание |
|--------|----------|
| **PersistentVolume (PV)** | Физический storage в кластере |
| **PersistentVolumeClaim (PVC)** | Запрос на storage от Pod'а |
| **StorageClass** | Шаблон для динамического создания PV |

> В нашем кластере: [[Longhorn]]

---

## Архитектура

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          KUBERNETES CLUSTER                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌───────────────────────────────────────────────────────────────┐     │
│   │                     CONTROL PLANE                              │     │
│   │                                                                │     │
│   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │     │
│   │   │ API Server  │  │  Scheduler  │  │ Controller Manager  │   │     │
│   │   │             │  │             │  │                     │   │     │
│   │   │ Входная     │  │ Назначает   │  │ Поддерживает        │   │     │
│   │   │ точка для   │  │ Pod'ы на    │  │ желаемое состояние  │   │     │
│   │   │ всех команд │  │ ноды        │  │                     │   │     │
│   │   └─────────────┘  └─────────────┘  └─────────────────────┘   │     │
│   │                                                                │     │
│   │   ┌─────────────────────────────────────────────────────────┐ │     │
│   │   │                        etcd                              │ │     │
│   │   │   Распределённая key-value БД для хранения состояния    │ │     │
│   │   └─────────────────────────────────────────────────────────┘ │     │
│   └───────────────────────────────────────────────────────────────┘     │
│                                                                          │
│   ┌───────────────────────────────────────────────────────────────┐     │
│   │                     WORKER NODES                               │     │
│   │                                                                │     │
│   │   ┌─────────────────────────────────────────────────────────┐ │     │
│   │   │  kubelet         │  kube-proxy       │  Container      │ │     │
│   │   │                  │                   │  Runtime        │ │     │
│   │   │  Запускает       │  Сетевой прокси   │  (containerd,   │ │     │
│   │   │  Pod'ы на ноде   │  для Service'ов   │   Docker, etc)  │ │     │
│   │   └─────────────────────────────────────────────────────────┘ │     │
│   │                                                                │     │
│   │   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │     │
│   │   │  Pod 1   │  │  Pod 2   │  │  Pod 3   │  │  Pod N   │     │     │
│   │   └──────────┘  └──────────┘  └──────────┘  └──────────┘     │     │
│   └───────────────────────────────────────────────────────────────┘     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Как работает развёртывание

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                           │
│  1. kubectl apply -f deployment.yaml                                     │
│                    │                                                      │
│                    ▼                                                      │
│  2. API Server принимает манифест, сохраняет в etcd                      │
│                    │                                                      │
│                    ▼                                                      │
│  3. Controller Manager видит: "нужно 3 реплики, есть 0"                  │
│     → создаёт 3 Pod'а                                                    │
│                    │                                                      │
│                    ▼                                                      │
│  4. Scheduler назначает Pod'ы на ноды                                    │
│     (учитывает ресурсы, affinity, taints)                                │
│                    │                                                      │
│                    ▼                                                      │
│  5. kubelet на каждой ноде запускает контейнеры                          │
│                    │                                                      │
│                    ▼                                                      │
│  6. kube-proxy настраивает iptables для Service                          │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Документация по темам

### Networking

| Документ | Описание |
|----------|----------|
| [[Kubernetes - Сеть и взаимодействие]] | Подробная теория: Pod'ы, Service'ы, DNS, cross-namespace |
| [[Services]] | Типы Service, порты, практика |
| [[Networking]] | Overlay networks, CNI |
| [[Ingress]] | HTTP routing, TLS |
| [[MetalLB]] | LoadBalancer для bare-metal |

### Workloads

| Документ | Описание |
|----------|----------|
| [[Deployments]] | Управление репликами, rolling updates |
| [[K3s - GPU Support]] | Запуск GPU workloads |

### Storage

| Документ | Описание |
|----------|----------|
| [[Longhorn]] | Distributed storage в нашем кластере |

### Security & Policy

| Документ | Описание |
|----------|----------|
| [[Kubernetes - Policy Engines]] | Kyverno, OPA Gatekeeper, PSS — сравнение и выбор |

### Наш кластер

| Документ | Описание |
|----------|----------|
| [[K3s]] | Обзор нашего кластера |
| [[K3s - Архитектура]] | Топология, взаимодействие сервисов |
| [[K3s - Установка HA]] | Инструкция по установке |
| [[K3s - kube-vip]] | Virtual IP для API |

---

## Дистрибутивы

| Дистрибутив | Описание | Использование |
|-------------|----------|---------------|
| [[K3s]] | Легковесный (100MB) | Homelab, Edge, IoT |
| K8s (vanilla) | Полноценный | Production |
| MicroK8s | От Canonical | Разработка, Ubuntu |
| Kind | K8s в Docker | CI/CD, тестирование |
| Minikube | Локальный кластер | Обучение |

---

## Команды kubectl

### Просмотр ресурсов

```bash
# Все Pod'ы во всех namespace
kubectl get pods -A

# Pod'ы с расширенной информацией (IP, Node)
kubectl get pods -o wide

# Все ресурсы в namespace
kubectl get all -n <namespace>

# Детальная информация
kubectl describe pod <name> -n <namespace>
kubectl describe svc <name> -n <namespace>
```

### Логи и отладка

```bash
# Логи Pod'а
kubectl logs <pod> -n <namespace>

# Логи с follow
kubectl logs -f <pod> -n <namespace>

# Логи конкретного контейнера (если несколько)
kubectl logs <pod> -c <container> -n <namespace>

# Shell в контейнер
kubectl exec -it <pod> -n <namespace> -- sh

# Проверить DNS
kubectl run dnstest --image=busybox --rm -it --restart=Never -- nslookup <service>.<namespace>
```

### Управление

```bash
# Применить манифест
kubectl apply -f manifest.yaml

# Удалить ресурс
kubectl delete -f manifest.yaml
kubectl delete pod <name> -n <namespace>

# Перезапустить Deployment
kubectl rollout restart deployment <name> -n <namespace>

# Масштабировать
kubectl scale deployment <name> --replicas=3 -n <namespace>
```

### Конфигурация

```bash
# Изменить Deployment
kubectl edit deployment <name> -n <namespace>

# Patch (изменить конкретное поле)
kubectl patch svc <name> -n <namespace> --type=json \
  -p='[{"op":"replace","path":"/spec/ports/0/targetPort","value":8080}]'

# Добавить env variable
kubectl set env deployment/<name> VAR=value -n <namespace>
```

---

## Ресурсы

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [kubectl Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)
- [Kubernetes The Hard Way](https://github.com/kelseyhightower/kubernetes-the-hard-way)

## См. также

- [[K3s]] — наш кластер
- [[Kubernetes - Сеть и взаимодействие]] — networking deep dive
- [[Docker]] — контейнеры
- [[Helm]] — пакетный менеджер

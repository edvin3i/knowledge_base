---
tags:
  - kubernetes
  - k3s
  - workloads
created: 2025-01-16
updated: 2026-01-24
---

# Deployments

Deployment — ресурс Kubernetes для декларативного управления Pod'ами. Обеспечивает rolling updates, откаты и масштабирование.

## Концепция

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DEPLOYMENT                                       │
│                                                                          │
│   apiVersion: apps/v1                                                   │
│   kind: Deployment                                                      │
│   metadata:                                                             │
│     name: my-app                                                        │
│   spec:                                                                 │
│     replicas: 3  ◄─────────────────────────────────────────────┐       │
│     selector:                                                   │       │
│       matchLabels:                                              │       │
│         app: my-app                                             │       │
│     template:  ◄── Pod Template                                 │       │
│       metadata:                                                 │       │
│         labels:                                                 │       │
│           app: my-app                                           │       │
│       spec:                                                     │       │
│         containers:                                             │       │
│         - name: app                                             │       │
│           image: my-app:v1                                      │       │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Deployment создаёт ReplicaSet, который управляет Pod'ами:             │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────┐      │
│   │  ReplicaSet (my-app-7f89d6c5b8)                              │      │
│   │                                                               │      │
│   │   ┌─────────┐   ┌─────────┐   ┌─────────┐                   │      │
│   │   │  Pod 1  │   │  Pod 2  │   │  Pod 3  │  ← replicas: 3    │      │
│   │   │ my-app  │   │ my-app  │   │ my-app  │                   │      │
│   │   └─────────┘   └─────────┘   └─────────┘                   │      │
│   └─────────────────────────────────────────────────────────────┘      │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

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

---

## Манифест Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: default
  labels:
    app: my-app
spec:
  replicas: 3

  # Стратегия обновления
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1        # Сколько Pod'ов можно создать сверх replicas
      maxUnavailable: 0  # Сколько Pod'ов может быть недоступно

  # Как найти Pod'ы этого Deployment
  selector:
    matchLabels:
      app: my-app

  # Шаблон для создания Pod'ов
  template:
    metadata:
      labels:
        app: my-app
    spec:
      containers:
      - name: app
        image: my-app:v1
        ports:
        - containerPort: 8080

        # Ресурсы
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "500m"

        # Health checks
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 10

        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5

        # Environment variables
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url
        - name: LOG_LEVEL
          value: "info"
```

---

## Rolling Updates

### Как работает обновление

```
┌─────────────────────────────────────────────────────────────────────────┐
│  kubectl set image deployment/my-app app=my-app:v2                      │
│                                                                          │
│  Шаг 1: Создаётся новый ReplicaSet                                      │
│  ─────────────────────────────────────────────────────────              │
│                                                                          │
│  ReplicaSet v1 (3 pods)          ReplicaSet v2 (0 pods)                 │
│  ┌────┐ ┌────┐ ┌────┐            (создан, но пустой)                   │
│  │Pod1│ │Pod2│ │Pod3│                                                   │
│  └────┘ └────┘ └────┘                                                   │
│                                                                          │
│  Шаг 2: Постепенная миграция (maxSurge=1, maxUnavailable=0)             │
│  ─────────────────────────────────────────────────────────              │
│                                                                          │
│  ReplicaSet v1 (3 pods)          ReplicaSet v2 (1 pod)                  │
│  ┌────┐ ┌────┐ ┌────┐            ┌────┐                                │
│  │Pod1│ │Pod2│ │Pod3│            │Pod4│ ← новый                        │
│  └────┘ └────┘ └────┘            └────┘   (ждём ready)                 │
│                                                                          │
│  ReplicaSet v1 (2 pods)          ReplicaSet v2 (2 pods)                 │
│  ┌────┐ ┌────┐                   ┌────┐ ┌────┐                         │
│  │Pod1│ │Pod2│                   │Pod4│ │Pod5│                         │
│  └────┘ └────┘                   └────┘ └────┘                         │
│                                                                          │
│  Шаг 3: Завершение                                                      │
│  ─────────────────────────────────────────────────────────              │
│                                                                          │
│  ReplicaSet v1 (0 pods)          ReplicaSet v2 (3 pods)                 │
│  (сохраняется для rollback)      ┌────┐ ┌────┐ ┌────┐                  │
│                                  │Pod4│ │Pod5│ │Pod6│                  │
│                                  └────┘ └────┘ └────┘                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Команды управления

```bash
# Обновить образ
kubectl set image deployment/my-app app=my-app:v2

# Следить за rollout
kubectl rollout status deployment/my-app

# История версий
kubectl rollout history deployment/my-app

# Откатить на предыдущую версию
kubectl rollout undo deployment/my-app

# Откатить на конкретную ревизию
kubectl rollout undo deployment/my-app --to-revision=2

# Приостановить rollout (для batch-изменений)
kubectl rollout pause deployment/my-app
kubectl set image deployment/my-app app=my-app:v2
kubectl set env deployment/my-app LOG_LEVEL=debug
kubectl rollout resume deployment/my-app
```

---

## Масштабирование

```bash
# Ручное масштабирование
kubectl scale deployment my-app --replicas=5

# Autoscaling (HPA)
kubectl autoscale deployment my-app --min=2 --max=10 --cpu-percent=80
```

---

## Environment Variables

### Добавить/изменить переменные

```bash
# Добавить переменную
kubectl set env deployment/my-app NEW_VAR=value

# Изменить существующую
kubectl set env deployment/my-app LOG_LEVEL=debug

# Удалить переменную
kubectl set env deployment/my-app LOG_LEVEL-

# Посмотреть все переменные
kubectl set env deployment/my-app --list
```

### Из Secret или ConfigMap

```bash
# Из Secret
kubectl set env deployment/my-app --from=secret/db-credentials

# Из ConfigMap
kubectl set env deployment/my-app --from=configmap/app-config
```

---

## Примеры из кластера

### CVAT Backend Server

```bash
# Посмотреть deployment
kubectl get deployment cvat-backend-server -n cvat -o yaml

# Environment variables
kubectl set env deployment/cvat-backend-server -n cvat --list

# Перезапустить после изменений
kubectl rollout restart deployment/cvat-backend-server -n cvat
```

### Nuclio Controller

```bash
# Статус
kubectl get deployment nuclio-controller -n cvat

# Логи
kubectl logs -n cvat -l app.kubernetes.io/name=nuclio-controller
```

---

## Troubleshooting

### Pod'ы не запускаются

```bash
# Статус Pod'ов
kubectl get pods -l app=my-app

# Детали Pod'а
kubectl describe pod <pod-name>

# Логи
kubectl logs <pod-name>

# События
kubectl get events --sort-by='.lastTimestamp'
```

### ImagePullBackOff

```bash
# Проверить image name
kubectl describe pod <pod-name> | grep -A 5 "Containers:"

# Проверить доступ к registry
kubectl get secret -n <namespace>
```

### CrashLoopBackOff

```bash
# Логи предыдущего контейнера
kubectl logs <pod-name> --previous

# Проверить liveness probe
kubectl describe pod <pod-name> | grep -A 10 "Liveness:"
```

---

## См. также

- [[Kubernetes]] — основные концепции
- [[Services]] — сетевой доступ к Pod'ам
- [[Kubernetes - Сеть и взаимодействие]] — теория networking
- [[K3s]] — наш кластер
- [[Ingress]] — HTTP routing

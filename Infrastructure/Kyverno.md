---
tags:
  - kubernetes
  - security
  - policy
  - infrastructure
created: 2026-01-28
updated: 2026-01-28
---

# Kyverno

Kubernetes-native policy engine для валидации, мутации и генерации ресурсов.

## Статус

| Параметр | Значение |
|----------|----------|
| **Версия** | 1.13.x |
| **Namespace** | `kyverno` |
| **CNCF** | Incubating |
| **Установлен** | ❌ Нет |

---

## Теория

> Подробное сравнение Policy Engines: [[Kubernetes - Policy Engines]]

### Что делает Kyverno

```
┌─────────────────────────────────────────────────────────────────┐
│                    Kyverno Architecture                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   kubectl apply / nuctl deploy / helm install                   │
│          │                                                       │
│          ▼                                                       │
│   ┌──────────────┐                                              │
│   │  API Server  │                                              │
│   └──────┬───────┘                                              │
│          │                                                       │
│          │ Admission Webhook                                     │
│          ▼                                                       │
│   ┌──────────────────────────────────────────────────┐          │
│   │                   Kyverno                         │          │
│   │                                                   │          │
│   │  ┌─────────────┐  ┌─────────────┐  ┌──────────┐  │          │
│   │  │  Validate   │  │   Mutate    │  │ Generate │  │          │
│   │  │             │  │             │  │          │  │          │
│   │  │ Отклонить   │  │ Изменить    │  │ Создать  │  │          │
│   │  │ ресурс      │  │ ресурс      │  │ ресурс   │  │          │
│   │  └─────────────┘  └─────────────┘  └──────────┘  │          │
│   │                                                   │          │
│   └──────────────────────────────────────────────────┘          │
│          │                                                       │
│          ▼                                                       │
│   Ресурс создан / отклонён / изменён                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Типы политик

| Тип | Действие | Пример |
|-----|----------|--------|
| **Validate** | Блокирует ресурсы не по правилам | Запретить `latest` tag |
| **Mutate** | Автоматически изменяет ресурсы | Добавить `runtimeClassName` |
| **Generate** | Создаёт дополнительные ресурсы | NetworkPolicy для namespace |
| **VerifyImages** | Проверяет подписи образов | Cosign/Notary verification |

### Компоненты

| Компонент | Назначение |
|-----------|------------|
| **Admission Controller** | Обрабатывает webhooks (validate/mutate) |
| **Background Controller** | Generate политики, периодические проверки |
| **Cleanup Controller** | Удаление ресурсов по TTL |
| **Reports Controller** | Генерация Policy Reports |

---

## Установка

### Предварительные требования

- Kubernetes 1.25+ (K3s подходит)
- Helm 3.x
- ~150-300 MB RAM в кластере

### Шаг 1: Добавить Helm репозиторий

```bash
helm repo add kyverno https://kyverno.github.io/kyverno/
helm repo update
```

### Шаг 2: Создать values файл

```bash
cat > /tmp/kyverno-values.yaml << 'EOF'
# Kyverno values для homelab K3s кластера

# Admission Controller
admissionController:
  replicas: 1  # Для homelab достаточно 1
  resources:
    limits:
      memory: 384Mi
    requests:
      cpu: 100m
      memory: 128Mi

# Background Controller
backgroundController:
  replicas: 1
  resources:
    limits:
      memory: 128Mi
    requests:
      cpu: 100m
      memory: 64Mi

# Cleanup Controller
cleanupController:
  replicas: 1
  resources:
    limits:
      memory: 128Mi
    requests:
      cpu: 100m
      memory: 64Mi

# Reports Controller
reportsController:
  replicas: 1
  resources:
    limits:
      memory: 128Mi
    requests:
      cpu: 100m
      memory: 64Mi

# Webhooks configuration
config:
  # Исключить системные namespace из политик
  webhooks:
    - namespaceSelector:
        matchExpressions:
        - key: kubernetes.io/metadata.name
          operator: NotIn
          values:
          - kube-system
          - kube-public
          - kube-node-lease
          - kyverno

# Включить Policy Reports
features:
  policyReports:
    enabled: true
EOF
```

**Разбор параметров:**

| Параметр | Значение | Зачем |
|----------|----------|-------|
| `replicas: 1` | 1 реплика | Для homelab достаточно, экономия ресурсов |
| `namespaceSelector` | Исключает системные ns | Не применять политики к kube-system |
| `policyReports` | enabled | Отчёты о применении политик |

### Шаг 3: Установить Kyverno

```bash
helm install kyverno kyverno/kyverno \
  --namespace kyverno \
  --create-namespace \
  -f /tmp/kyverno-values.yaml
```

### Шаг 4: Дождаться готовности

```bash
# Проверить статус установки
kubectl get pods -n kyverno -w

# Ожидаемый вывод (через 1-2 минуты):
# NAME                                             READY   STATUS    RESTARTS   AGE
# kyverno-admission-controller-xxx                 1/1     Running   0          60s
# kyverno-background-controller-xxx                1/1     Running   0          60s
# kyverno-cleanup-controller-xxx                   1/1     Running   0          60s
# kyverno-reports-controller-xxx                   1/1     Running   0          60s
```

### Шаг 5: Проверить webhooks

```bash
# Validating webhook
kubectl get validatingwebhookconfigurations | grep kyverno

# Mutating webhook
kubectl get mutatingwebhookconfigurations | grep kyverno

# Ожидаемо:
# kyverno-policy-validating-webhook-cfg
# kyverno-resource-validating-webhook-cfg
# kyverno-resource-mutating-webhook-cfg
```

---

## Применение политики для Nuclio GPU

Основная причина установки — автоматическое добавление `runtimeClassName: nvidia` для GPU функций Nuclio.

### Создать политику

```bash
kubectl apply -f - << 'EOF'
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: add-nvidia-runtime-class
  annotations:
    policies.kyverno.io/title: Add NVIDIA RuntimeClass to GPU Deployments
    policies.kyverno.io/category: Nuclio
    policies.kyverno.io/description: >-
      Nuclio controller не передаёт runtimeClassName в Deployment.
      Эта политика автоматически добавляет runtimeClassName: nvidia
      для всех deployments в namespace cvat с nvidia.com/gpu resource.
spec:
  rules:
  - name: add-runtime-class-to-gpu-pods
    match:
      resources:
        kinds:
        - Deployment
        namespaces:
        - cvat
    preconditions:
      all:
      # Проверяем что есть GPU request в первом контейнере
      - key: "{{ request.object.spec.template.spec.containers[0].resources.limits.\"nvidia.com/gpu\" || '0' }}"
        operator: GreaterThanOrEquals
        value: "1"
    mutate:
      patchStrategicMerge:
        spec:
          template:
            spec:
              runtimeClassName: nvidia
EOF
```

### Проверить политику

```bash
# Политика создана
kubectl get clusterpolicy add-nvidia-runtime-class

# Детали политики
kubectl describe clusterpolicy add-nvidia-runtime-class
```

### Тестирование

```bash
# 1. Задеплоить GPU функцию через nuctl
nuctl deploy --project-name cvat \
  --path /path/to/serverless/gpu-function \
  --namespace cvat \
  --platform kube \
  --registry docker.io/edvin3i

# 2. Проверить что runtimeClassName добавлен автоматически
kubectl get deployment nuclio-<func-name> -n cvat \
  -o jsonpath='{.spec.template.spec.runtimeClassName}'
# Ожидаемо: nvidia

# 3. Проверить CUDA в контейнере
POD=$(kubectl get pods -n cvat -l nuclio.io/function-name=<func-name> \
  -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n cvat $POD -- python3 -c "import torch; print('CUDA:', torch.cuda.is_available())"
# Ожидаемо: CUDA: True
```

---

## Дополнительные политики

### Запретить privileged контейнеры

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: disallow-privileged-containers
spec:
  validationFailureAction: Enforce  # Блокировать, не просто warning
  rules:
  - name: deny-privileged
    match:
      resources:
        kinds:
        - Pod
    validate:
      message: "Privileged containers are not allowed"
      pattern:
        spec:
          containers:
          - securityContext:
              privileged: "!true"
```

### Требовать resource limits

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-resource-limits
spec:
  validationFailureAction: Audit  # Только warning, не блокировать
  rules:
  - name: require-limits
    match:
      resources:
        kinds:
        - Pod
    validate:
      message: "Resource limits are required"
      pattern:
        spec:
          containers:
          - resources:
              limits:
                memory: "?*"
                cpu: "?*"
```

### Автодобавление labels

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: add-default-labels
spec:
  rules:
  - name: add-managed-by
    match:
      resources:
        kinds:
        - Deployment
        - StatefulSet
    mutate:
      patchStrategicMerge:
        metadata:
          labels:
            +(app.kubernetes.io/managed-by): "kyverno"
```

---

## Мониторинг

### Policy Reports

Kyverno создаёт отчёты о применении политик:

```bash
# Все отчёты
kubectl get policyreport -A

# Отчёт для namespace
kubectl get policyreport -n cvat

# Детали (показывает pass/fail/warn)
kubectl describe policyreport -n cvat
```

### Логи

```bash
# Admission controller (validate/mutate)
kubectl logs -n kyverno -l app.kubernetes.io/component=admission-controller --tail=50

# Background controller (generate)
kubectl logs -n kyverno -l app.kubernetes.io/component=background-controller --tail=50

# С follow
kubectl logs -n kyverno -l app.kubernetes.io/component=admission-controller -f
```

### Метрики (опционально)

Kyverno экспортирует Prometheus метрики:

```bash
# Порт метрик
kubectl port-forward -n kyverno svc/kyverno-svc-metrics 8000:8000

# Проверить
curl http://localhost:8000/metrics | grep kyverno
```

---

## Обновление

```bash
# Обновить репозиторий
helm repo update

# Проверить доступные версии
helm search repo kyverno/kyverno --versions | head -5

# Обновить
helm upgrade kyverno kyverno/kyverno \
  --namespace kyverno \
  -f /tmp/kyverno-values.yaml
```

---

## Удаление

```bash
# Удалить Kyverno
helm uninstall kyverno -n kyverno

# Удалить CRDs (политики удалятся вместе с ними)
kubectl delete crd clusterpolicies.kyverno.io
kubectl delete crd policies.kyverno.io
kubectl delete crd policyreports.wgpolicyk8s.io
kubectl delete crd clusterpolicyreports.wgpolicyk8s.io

# Удалить namespace
kubectl delete namespace kyverno

# Удалить webhooks (если остались)
kubectl delete validatingwebhookconfiguration -l app.kubernetes.io/instance=kyverno
kubectl delete mutatingwebhookconfiguration -l app.kubernetes.io/instance=kyverno
```

---

## Troubleshooting

### Политика не применяется

**Симптом:** Deployment создаётся без изменений от mutate политики.

**Диагностика:**

```bash
# Проверить что политика ready
kubectl get clusterpolicy add-nvidia-runtime-class -o jsonpath='{.status.ready}'
# Должно быть: true

# Проверить логи admission controller
kubectl logs -n kyverno -l app.kubernetes.io/component=admission-controller --tail=100 | grep -i "add-nvidia"

# Проверить Policy Report
kubectl get policyreport -n cvat -o yaml | grep -A10 "add-nvidia-runtime-class"
```

**Частые причины:**
1. Namespace исключён в webhooks config
2. Preconditions не совпадают (проверить путь к GPU resource)
3. Webhook не зарегистрирован

### Webhook timeout

**Симптом:** `Error from server: Internal error occurred: failed calling webhook`

**Решение:**

```bash
# Проверить что поды running
kubectl get pods -n kyverno

# Рестартнуть если нужно
kubectl rollout restart deployment -n kyverno -l app.kubernetes.io/instance=kyverno

# Проверить что webhook endpoint доступен
kubectl get endpoints -n kyverno
```

### Высокое потребление памяти

**Симптом:** OOMKilled pods.

**Решение:**

```bash
# Увеличить limits в values
helm upgrade kyverno kyverno/kyverno \
  --namespace kyverno \
  --set admissionController.resources.limits.memory=512Mi \
  --set backgroundController.resources.limits.memory=256Mi
```

---

## Полезные команды

```bash
# Список всех политик
kubectl get clusterpolicy

# Детали политики
kubectl describe clusterpolicy <name>

# Проверить что политика применилась к ресурсу
kubectl get deployment <name> -n <ns> -o yaml | grep -A5 runtimeClassName

# Тестировать политику локально (нужен kyverno CLI)
# Установка: kubectl krew install kyverno
kubectl kyverno apply policy.yaml --resource deployment.yaml

# Dry-run: посмотреть что сделает политика
kubectl kyverno apply policy.yaml --resource deployment.yaml -o yaml
```

---

## Ссылки

- [Kyverno Documentation](https://kyverno.io/docs/)
- [Kyverno Policies Library](https://kyverno.io/policies/)
- [Kyverno GitHub](https://github.com/kyverno/kyverno)
- [Kyverno Playground](https://playground.kyverno.io/) — тестировать политики онлайн

---

## См. также

- [[Kubernetes - Policy Engines]] — сравнение с Gatekeeper, PSS
- [[CVAT]] — проблема с Nuclio runtimeClassName
- [[K3s - GPU Support]]
- [[Kubernetes]]

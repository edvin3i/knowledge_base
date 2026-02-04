---
tags:
  - kubernetes
  - security
  - policy
  - infrastructure
created: 2026-01-28
updated: 2026-01-28
---

# Kubernetes - Policy Engines

Policy Engines позволяют декларативно управлять тем, какие ресурсы могут быть созданы в кластере и как они должны быть настроены.

## Зачем нужны Policy Engines

### Проблема

Kubernetes по умолчанию разрешает создавать любые ресурсы с любыми параметрами:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Без Policy Engine                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Developer                                                      │
│       │                                                          │
│       │ kubectl apply -f deployment.yaml                        │
│       │ (privileged: true, image: latest, no limits)            │
│       ▼                                                          │
│   ┌──────────────┐                                              │
│   │  API Server  │  → Принимает всё ✓                           │
│   └──────────────┘                                              │
│                                                                  │
│   Проблемы:                                                      │
│   - Privileged контейнеры (security risk)                       │
│   - Нет resource limits (noisy neighbors)                       │
│   - latest тег (непредсказуемые деплои)                         │
│   - Нет required labels (хаос в мониторинге)                    │
│   - Nuclio не передаёт runtimeClassName (GPU не работает)       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Решение

Policy Engine перехватывает запросы к API Server и может:

1. **Validate** — отклонить ресурс, не соответствующий правилам
2. **Mutate** — автоматически изменить ресурс (добавить labels, limits, и т.д.)
3. **Generate** — создать дополнительные ресурсы (NetworkPolicy, RBAC)

```
┌─────────────────────────────────────────────────────────────────┐
│                    С Policy Engine                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Developer                                                      │
│       │                                                          │
│       │ kubectl apply / nuctl deploy / helm install             │
│       ▼                                                          │
│   ┌──────────────┐                                              │
│   │  API Server  │                                              │
│   └──────┬───────┘                                              │
│          │                                                       │
│          │ Admission Webhook                                     │
│          ▼                                                       │
│   ┌──────────────────────────────────────────────────┐          │
│   │              Policy Engine                        │          │
│   │                                                   │          │
│   │  ┌─────────────────────────────────────────────┐ │          │
│   │  │ Policy: add-nvidia-runtime                   │ │          │
│   │  │ IF resources.limits["nvidia.com/gpu"] > 0   │ │          │
│   │  │ THEN add runtimeClassName: nvidia           │ │          │
│   │  └─────────────────────────────────────────────┘ │          │
│   │                                                   │          │
│   │  ┌─────────────────────────────────────────────┐ │          │
│   │  │ Policy: require-resource-limits             │ │          │
│   │  │ IF no limits defined                        │ │          │
│   │  │ THEN reject with message                    │ │          │
│   │  └─────────────────────────────────────────────┘ │          │
│   └──────────────────────────────────────────────────┘          │
│          │                                                       │
│          ▼                                                       │
│   Ресурс создан (уже с нужными параметрами)                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Сравнение Policy Engines

### Обзор вариантов

| Engine | Разработчик | Язык политик | Год | Статус |
|--------|-------------|--------------|-----|--------|
| **Kyverno** | Nirmata | YAML | 2019 | CNCF Incubating |
| **OPA Gatekeeper** | Styra/CNCF | Rego | 2018 | CNCF Graduated |
| **Pod Security Standards** | Kubernetes | Labels | 2021 | Встроен в K8s |
| **Kubewarden** | SUSE | WebAssembly | 2021 | CNCF Sandbox |
| **Polaris** | Fairwinds | YAML/JSON | 2019 | Open Source |
| **jsPolicy** | Loft Labs | JavaScript | 2021 | Open Source |

### Детальное сравнение

#### 1. Kyverno

**Что это:** Policy engine с политиками на чистом YAML.

**Возможности:**
- Validate (проверка)
- Mutate (изменение)
- Generate (генерация ресурсов)
- Image verification (подпись образов)

**Пример политики:**
```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: add-nvidia-runtime
spec:
  rules:
  - name: add-runtime-class
    match:
      resources:
        kinds: [Deployment]
    preconditions:
      all:
      - key: "{{ request.object.spec.template.spec.containers[0].resources.limits.\"nvidia.com/gpu\" || '' }}"
        operator: GreaterThan
        value: "0"
    mutate:
      patchStrategicMerge:
        spec:
          template:
            spec:
              runtimeClassName: nvidia
```

**Плюсы:**
- Политики на YAML — не нужно учить новый язык
- Поддерживает mutate и generate
- Хорошая документация
- Активное сообщество (CNCF Incubating)
- Встроенная библиотека готовых политик

**Минусы:**
- Сложная логика требует вложенных условий
- Меньше гибкости чем Rego
- Относительно молодой проект

**Ресурсы:**
- ~100-300 MB RAM (зависит от количества политик)
- 2-3 пода (admission controller, background controller, reports controller)

---

#### 2. OPA Gatekeeper

**Что это:** Kubernetes-адаптер для Open Policy Agent с языком Rego.

**Возможности:**
- Validate (проверка)
- Audit (проверка существующих ресурсов)
- External data (запросы к внешним API)

**Пример политики:**
```yaml
# ConstraintTemplate (определяет логику на Rego)
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: k8srequiredlabels
spec:
  crd:
    spec:
      names:
        kind: K8sRequiredLabels
      validation:
        openAPIV3Schema:
          properties:
            labels:
              type: array
              items: string
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        package k8srequiredlabels

        violation[{"msg": msg}] {
          provided := {label | input.review.object.metadata.labels[label]}
          required := {label | label := input.parameters.labels[_]}
          missing := required - provided
          count(missing) > 0
          msg := sprintf("Missing required labels: %v", [missing])
        }
---
# Constraint (применяет логику)
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sRequiredLabels
metadata:
  name: require-team-label
spec:
  match:
    kinds:
    - apiGroups: [""]
      kinds: ["Pod"]
  parameters:
    labels: ["team"]
```

**Плюсы:**
- Rego очень мощный (любая логика)
- CNCF Graduated (зрелый проект)
- Может использовать внешние данные
- OPA используется не только в K8s

**Минусы:**
- Нужно учить Rego (специфический язык)
- **Не поддерживает mutate** (только validate)
- Сложнее в отладке
- Больше YAML (ConstraintTemplate + Constraint)

**Ресурсы:**
- ~200-500 MB RAM
- audit controller потребляет больше при большом количестве ресурсов

---

#### 3. Pod Security Standards (PSS)

**Что это:** Встроенный в Kubernetes механизм security policies.

**Уровни:**
- `privileged` — без ограничений
- `baseline` — минимальные ограничения (запрет privileged, hostNetwork, etc.)
- `restricted` — строгие ограничения (non-root, read-only filesystem, etc.)

**Применение:**
```yaml
# На уровне namespace
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/audit: restricted
```

**Плюсы:**
- Встроен в Kubernetes (с v1.25)
- Не требует установки
- Нулевой overhead

**Минусы:**
- **Только security policies** (не mutate, не custom validation)
- Только 3 предустановленных уровня
- Нет кастомизации правил
- Не решает проблему Nuclio/runtimeClassName

---

#### 4. Kubewarden

**Что это:** Policy engine с политиками на WebAssembly.

**Плюсы:**
- Политики можно писать на любом языке (Rust, Go, AssemblyScript)
- Политики как переиспользуемые артефакты (OCI registry)
- Поддерживает mutate

**Минусы:**
- Нужно компилировать политики в WASM
- Меньше сообщество
- Более сложная разработка политик

---

#### 5. Polaris

**Что это:** Инструмент для проверки best practices.

**Плюсы:**
- Готовые checks из коробки
- Dashboard для визуализации
- Может работать как CLI, webhook или in-cluster

**Минусы:**
- Фокус на best practices, не custom policies
- Нет mutate
- Менее гибкий

---

#### 6. jsPolicy

**Что это:** Policy engine с политиками на JavaScript/TypeScript.

**Плюсы:**
- JavaScript — популярный язык
- Поддерживает mutate

**Минусы:**
- Меньше сообщество
- Зависимость от V8 engine

---

## Сводная таблица

| Критерий | Kyverno | OPA Gatekeeper | PSS | Kubewarden |
|----------|---------|----------------|-----|------------|
| **Validate** | ✅ | ✅ | ✅ | ✅ |
| **Mutate** | ✅ | ❌ | ❌ | ✅ |
| **Generate** | ✅ | ❌ | ❌ | ❌ |
| **Язык** | YAML | Rego | Labels | Any→WASM |
| **Порог входа** | Низкий | Высокий | Минимальный | Средний |
| **Гибкость** | Высокая | Очень высокая | Низкая | Очень высокая |
| **Сообщество** | Активное | Очень активное | N/A | Растущее |
| **CNCF** | Incubating | Graduated | Core | Sandbox |
| **RAM** | ~150MB | ~300MB | 0 | ~100MB |

---

## Наш выбор: Kyverno

### Почему Kyverno

Для задачи **автоматического добавления `runtimeClassName: nvidia`** в Nuclio функции:

| Требование | Kyverno | Gatekeeper | PSS | Bash-скрипт |
|------------|---------|------------|-----|-------------|
| Mutate deployment | ✅ | ❌ | ❌ | ✅ (после факта) |
| Автоматически | ✅ | - | - | ❌ |
| Без race condition | ✅ | - | - | ❌ |
| Не нужен новый язык | ✅ | ❌ (Rego) | ✅ | ✅ |
| Полезен для других задач | ✅ | ✅ | ограничено | ❌ |

**Gatekeeper не подходит** — не поддерживает mutate, мы не можем изменить Deployment.

**PSS не подходит** — только security policies, не кастомная логика.

**Bash-скрипт работает**, но:
- Нужно помнить запускать после каждого `nuctl deploy`
- Race condition — deployment создаётся, потом патчится
- Не масштабируется на другие задачи

### Дополнительные применения Kyverno

После установки Kyverno можно использовать для:

**1. Security defaults:**
```yaml
# Запретить privileged контейнеры
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: disallow-privileged
spec:
  validationFailureAction: Enforce
  rules:
  - name: deny-privileged
    match:
      resources:
        kinds: [Pod]
    validate:
      message: "Privileged containers are not allowed"
      pattern:
        spec:
          containers:
          - securityContext:
              privileged: "!true"
```

**2. Автодобавление labels:**
```yaml
# Добавить environment label
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: add-environment-label
spec:
  rules:
  - name: add-env
    match:
      resources:
        kinds: [Deployment, StatefulSet]
    mutate:
      patchStrategicMerge:
        metadata:
          labels:
            environment: "{{ request.namespace }}"
```

**3. Default resource limits:**
```yaml
# Добавить limits если не указаны
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: add-default-limits
spec:
  rules:
  - name: add-limits
    match:
      resources:
        kinds: [Pod]
    mutate:
      patchStrategicMerge:
        spec:
          containers:
          - (name): "*"
            resources:
              limits:
                +(memory): "512Mi"
                +(cpu): "500m"
```

**4. Автогенерация NetworkPolicy:**
```yaml
# Создать NetworkPolicy для каждого namespace
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: generate-network-policy
spec:
  rules:
  - name: default-deny
    match:
      resources:
        kinds: [Namespace]
    generate:
      kind: NetworkPolicy
      name: default-deny-ingress
      namespace: "{{ request.object.metadata.name }}"
      data:
        spec:
          podSelector: {}
          policyTypes:
          - Ingress
```

---

## Установка Kyverno

### Через Helm

```bash
# Добавить репозиторий
helm repo add kyverno https://kyverno.github.io/kyverno/
helm repo update

# Установить (рекомендуемый способ)
helm install kyverno kyverno/kyverno \
  --namespace kyverno \
  --create-namespace \
  --set replicaCount=1  # Для homelab достаточно 1 реплики
```

### Проверка

```bash
# Поды
kubectl get pods -n kyverno
# NAME                                             READY   STATUS
# kyverno-admission-controller-xxx                 1/1     Running
# kyverno-background-controller-xxx                1/1     Running
# kyverno-cleanup-controller-xxx                   1/1     Running
# kyverno-reports-controller-xxx                   1/1     Running

# Webhook зарегистрирован
kubectl get validatingwebhookconfigurations | grep kyverno
kubectl get mutatingwebhookconfigurations | grep kyverno
```

### Политика для Nuclio GPU функций

```yaml
# nuclio-gpu-runtime-policy.yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: add-nvidia-runtime-class
  annotations:
    policies.kyverno.io/title: Add NVIDIA RuntimeClass to GPU Deployments
    policies.kyverno.io/description: >-
      Nuclio controller не передаёт runtimeClassName в Deployment.
      Эта политика автоматически добавляет runtimeClassName: nvidia
      для всех deployments с nvidia.com/gpu resource.
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
      - key: "{{ request.object.spec.template.spec.containers[0].resources.limits.\"nvidia.com/gpu\" || '' }}"
        operator: GreaterThan
        value: "0"
    mutate:
      patchStrategicMerge:
        spec:
          template:
            spec:
              runtimeClassName: nvidia
```

```bash
# Применить
kubectl apply -f nuclio-gpu-runtime-policy.yaml

# Проверить
kubectl get clusterpolicy add-nvidia-runtime-class
```

### Тестирование

```bash
# Задеплоить GPU функцию
nuctl deploy --project-name cvat \
  --path /path/to/serverless/gpu-function \
  --namespace cvat \
  --platform kube

# Проверить что runtimeClassName добавлен автоматически
kubectl get deployment nuclio-<func-name> -n cvat \
  -o jsonpath='{.spec.template.spec.runtimeClassName}'
# nvidia

# Проверить CUDA в контейнере
POD=$(kubectl get pods -n cvat -l nuclio.io/function-name=<func-name> -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n cvat $POD -- python3 -c "import torch; print('CUDA:', torch.cuda.is_available())"
# CUDA: True
```

---

## Мониторинг и отладка

### Policy Reports

Kyverno создаёт отчёты о применении политик:

```bash
# Все отчёты в namespace
kubectl get policyreport -n cvat

# Детали отчёта
kubectl describe policyreport -n cvat
```

### Логи

```bash
# Логи admission controller
kubectl logs -n kyverno -l app.kubernetes.io/component=admission-controller

# Логи background controller (для generate)
kubectl logs -n kyverno -l app.kubernetes.io/component=background-controller
```

### Тестирование политик без применения

```bash
# Установить kyverno CLI
kubectl krew install kyverno

# Протестировать политику на ресурсе
kubectl kyverno apply policy.yaml --resource deployment.yaml
```

---

## Установка Kyverno

Пошаговая инструкция: [[Kyverno]]

## Полезные ссылки

- [Kyverno Documentation](https://kyverno.io/docs/)
- [Kyverno Policies Library](https://kyverno.io/policies/)
- [OPA Gatekeeper](https://open-policy-agent.github.io/gatekeeper/)
- [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [Kubewarden](https://www.kubewarden.io/)
- [Comparison: Kyverno vs Gatekeeper](https://neonmirrors.net/post/2021-02/kubernetes-policy-comparison-opa-gatekeeper-vs-kyverno/)

---

## См. также

- [[Kubernetes]]
- [[K3s]]
- [[Kyverno]] — установка и настройка
- [[CVAT]] — проблема с Nuclio runtimeClassName
- [[K3s - GPU Support]]
- [[Security]]

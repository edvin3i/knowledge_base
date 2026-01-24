---
tags:
  - kubernetes
  - infrastructure
  - homelab
  - gpu
  - nvidia
created: 2026-01-24
updated: 2026-01-24
---

# K3s - GPU Sharing

Как разделить один GPU между несколькими подами в [[K3s]] кластере.

## Проблема: один GPU — один под

По умолчанию Kubernetes выделяет GPU **эксклюзивно**:

```
┌─────────────────────────────────────────────────────────────┐
│                     RTX A6000 (48 GB)                        │
│                                                              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │         Pod: nuclio-yolo11x (использует 4 GB)        │   │
│   │                                                      │   │
│   │         44 GB простаивают!                           │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                              │
│   Другие поды: "Insufficient nvidia.com/gpu"                 │
│   (не могут запуститься)                                     │
└─────────────────────────────────────────────────────────────┘
```

**Почему так?**

Kubernetes видит GPU как **неделимый ресурс**:
- `nvidia.com/gpu: 1` = "дай мне весь GPU"
- Нельзя попросить `nvidia.com/gpu: 0.5`
- Device Plugin сообщает: "есть 1 GPU" — и всё

---

## Три способа разделить GPU

NVIDIA предоставляет три технологии для sharing:

| Технология | Изоляция памяти | Изоляция ошибок | Поддержка RTX A6000 |
|------------|-----------------|-----------------|---------------------|
| **Time-Slicing** | Нет | Нет | Да |
| **MPS** | Частичная | Нет | Да |
| **MIG** | Полная | Полная | Нет |

---

## 1. Time-Slicing (рекомендуется для A6000)

### Что это такое

**Time-Slicing** — переключение контекста на уровне GPU. Поды получают GPU **по очереди**, как процессы получают CPU.

```
Время →
┌────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┐
│ P1 │ P2 │ P3 │ P4 │ P1 │ P2 │ P3 │ P4 │ P1 │ P2 │ P3 │ P4 │
└────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┴────┘
  │    │    │    │
  │    │    │    └── Pod 4: FFmpeg NVENC
  │    │    └─────── Pod 3: Real-ESRGAN
  │    └──────────── Pod 2: RIFE
  └───────────────── Pod 1: YOLO (Nuclio)
```

### Как это работает на уровне железа

Начиная с архитектуры **Pascal** (2016), NVIDIA GPU поддерживают **instruction-level preemption**:

1. GPU выполняет инструкции от Pod 1
2. По сигналу прерывания сохраняет состояние (регистры, указатели)
3. Загружает состояние Pod 2
4. Выполняет инструкции Pod 2
5. Повторяет цикл

**Важно:** Память (VRAM) **не изолирована** — все поды видят общие 48 GB.

### Плюсы и минусы

| Плюсы | Минусы |
|-------|--------|
| Простая настройка | Нет изоляции памяти |
| Работает на любом GPU (Pascal+) | Один под может съесть всю VRAM |
| Не требует перезагрузки | Добавляет latency (context switch) |
| Можно задать любое количество "виртуальных" GPU | Нет гарантий QoS |

### Когда использовать

- Jupyter notebooks (интерактивная работа)
- CI/CD тесты (короткие задачи)
- Batch inference (не realtime)
- Workloads с разным временем активности (YOLO ждёт запросов, RIFE обрабатывает видео)

### Когда НЕ использовать

- Realtime inference с жёсткими требованиями к latency
- Workloads, которые используют всю VRAM
- Production с требованием fault isolation

---

## 2. MPS (Multi-Process Service)

### Что это такое

**MPS** — демон NVIDIA, который позволяет CUDA-процессам выполняться **параллельно** на GPU, а не последовательно.

```
Time-Slicing:                    MPS:
┌────┬────┬────┬────┐           ┌────────────────────────┐
│ P1 │ P2 │ P1 │ P2 │           │ P1   P2   P1   P2      │
└────┴────┴────┴────┘           │ ↓    ↓    ↓    ↓       │
Последовательно                 │ [одновременно на SM]   │
                                └────────────────────────┘
```

### Как это работает

GPU имеет много **SM** (Streaming Multiprocessors). Обычно один процесс занимает все SM. MPS позволяет разным процессам использовать **разные SM одновременно**:

```
RTX A6000: 84 SM
┌──────────────────────────────────────────────────────────┐
│ SM 0-20:  Process 1 (YOLO)                               │
│ SM 21-40: Process 2 (RIFE)                               │
│ SM 41-60: Process 3 (Real-ESRGAN)                        │
│ SM 61-83: Свободны                                       │
└──────────────────────────────────────────────────────────┘
```

### Настройка лимитов (CUDA 11.4+)

MPS поддерживает ограничение ресурсов:

```bash
# Ограничить память для клиента
export CUDA_MPS_PINNED_DEVICE_MEM_LIMIT=0_8192M  # 8 GB для GPU 0

# Ограничить compute (процент SM)
export CUDA_MPS_ACTIVE_THREAD_PERCENTAGE=25      # 25% SM
```

### Плюсы и минусы

| Плюсы | Минусы |
|-------|--------|
| Истинный параллелизм (не time-slicing) | Сложнее настроить |
| Меньше latency | Нет изоляции ошибок (crash = все падают) |
| Можно лимитировать память и compute | Требует MPS daemon |
| Эффективнее для мелких задач | Не работает с MIG |

### Когда использовать

- Много мелких inference-запросов
- MPI workloads (HPC)
- Когда один процесс не насыщает GPU

### Статус в Kubernetes

MPS в Kubernetes **экспериментальный**. Требует:
- Запуск MPS daemon как DaemonSet
- Настройка shared memory
- Пока есть баги (особенно на OpenShift)

---

## 3. MIG (Multi-Instance GPU)

### Что это такое

**MIG** — аппаратное разделение GPU на изолированные **инстансы**. Каждый инстанс имеет:
- Свои SM (compute)
- Свою память (VRAM)
- Свои контроллеры памяти

```
A100 (80 GB) с MIG:
┌─────────────────────────────────────────────────────────┐
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐ │
│ │ MIG 1g.10gb │ │ MIG 1g.10gb │ │     MIG 3g.40gb     │ │
│ │   Pod 1     │ │   Pod 2     │ │       Pod 3         │ │
│ │   10 GB     │ │   10 GB     │ │       40 GB         │ │
│ └─────────────┘ └─────────────┘ └─────────────────────┘ │
│      Полная изоляция — как отдельные GPU                 │
└─────────────────────────────────────────────────────────┘
```

### Поддерживаемые GPU

**MIG поддерживается ТОЛЬКО на datacenter GPU:**

| GPU                    | MIG     | Макс. инстансов |
| ---------------------- | ------- | --------------- |
| A100                   | Да      | 7               |
| A30                    | Да      | 4               |
| H100                   | Да      | 7               |
| H200                   | Да      | 7               |
| **RTX A6000**          | **Нет** | —               |
| RTX 4090               | Нет     | —               |
| RTX PRO 6000 Blackwell | Да      | 4               |

### Почему A6000 не поддерживает MIG

MIG требует специальной hardware логики в GPU. NVIDIA добавила её только в datacenter линейку (A100+), чтобы:
- Разделить продуктовые линейки (workstation vs datacenter)
- Обеспечить hardware-level изоляцию (сложнее в реализации)

### Плюсы и минусы

| Плюсы | Минусы |
|-------|--------|
| Полная изоляция памяти | Только A100/H100 |
| Полная изоляция ошибок | Фиксированные профили |
| Гарантированный QoS | Требует перезагрузки для изменения |
| Каждый инстанс = отдельный GPU в K8s | Сложная настройка |

---

## Сравнительная таблица

| Критерий | Time-Slicing | MPS | MIG |
|----------|--------------|-----|-----|
| **Изоляция памяти** | Нет | Частичная (лимиты) | Полная |
| **Изоляция ошибок** | Нет | Нет | Полная |
| **Параллелизм** | Нет (по очереди) | Да | Да |
| **Latency** | Выше (context switch) | Низкая | Низкая |
| **Гибкость** | Любое кол-во реплик | Любое кол-во | Фиксированные профили |
| **RTX A6000** | Да | Да | Нет |
| **Сложность** | Низкая | Средняя | Высокая |

---

## Рекомендация для нашего кластера

### Конфигурация

- **GPU:** RTX A6000 (48 GB VRAM)
- **Workloads:** YOLO (Nuclio), RIFE, Real-ESRGAN, FFmpeg

### Выбор: Time-Slicing

**Почему:**
1. MIG не поддерживается на A6000
2. MPS сложнее и имеет баги в K8s
3. Time-Slicing просто настроить
4. 48 GB VRAM достаточно для 4+ workloads

### Расчёт памяти

| Workload | Типичное потребление |
|----------|---------------------|
| YOLO11x (Nuclio) | 4-6 GB |
| RIFE (4K) | 6-8 GB |
| Real-ESRGAN | 4-6 GB |
| FFmpeg NVENC | 0.5 GB |
| **Итого** | ~20 GB из 48 GB |

**Запас есть** — можно безопасно использовать `replicas: 4`.

---

## Настройка Time-Slicing

### Шаг 1: Создание ConfigMap

ConfigMap содержит конфигурацию для Device Plugin:

```bash
kubectl apply -f - << 'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: nvidia-device-plugin-config
  namespace: kube-system
data:
  config.yaml: |
    version: v1
    flags:
      migStrategy: none
    sharing:
      timeSlicing:
        renameByDefault: false
        failRequestsGreaterThanOne: false
        resources:
        - name: nvidia.com/gpu
          replicas: 4
EOF
```

**Разбор конфигурации:**

| Поле | Значение | Объяснение |
|------|----------|------------|
| `version: v1` | Версия формата | Должна быть `v1` |
| `migStrategy: none` | Не использовать MIG | A6000 не поддерживает |
| `renameByDefault: false` | Не переименовывать ресурс | Оставить `nvidia.com/gpu` |
| `failRequestsGreaterThanOne: false` | Разрешить запрос >1 GPU | Для совместимости |
| `replicas: 4` | Количество виртуальных GPU | 1 физический → 4 логических |

**Что делает `replicas: 4`:**

```
До:                              После:
nvidia.com/gpu: 1                nvidia.com/gpu: 4

Scheduler видит 1 GPU            Scheduler видит 4 GPU
→ 1 под с GPU                    → 4 пода с GPU
```

### Шаг 2: Применение ConfigMap к Device Plugin

Device Plugin должен загрузить конфигурацию:

```bash
kubectl patch daemonset nvidia-device-plugin-daemonset -n kube-system \
    --type='json' \
    -p='[
      {"op": "add", "path": "/spec/template/spec/volumes/-", "value": {"name": "config", "configMap": {"name": "nvidia-device-plugin-config"}}},
      {"op": "add", "path": "/spec/template/spec/containers/0/volumeMounts/-", "value": {"name": "config", "mountPath": "/config"}},
      {"op": "replace", "path": "/spec/template/spec/containers/0/args", "value": ["--config-file=/config/config.yaml"]}
    ]'
```

**Разбор патча:**

| Операция | Что делает |
|----------|------------|
| `volumes/-` | Добавить volume с ConfigMap |
| `volumeMounts/-` | Примонтировать в контейнер |
| `args` | Указать путь к конфигу |

**Альтернатива:** пересоздать DaemonSet вручную (если patch не работает).

### Шаг 3: Перезапуск Device Plugin

```bash
kubectl rollout restart daemonset nvidia-device-plugin-daemonset -n kube-system
```

Подождать пока под перезапустится:

```bash
kubectl rollout status daemonset nvidia-device-plugin-daemonset -n kube-system
```

### Шаг 4: Проверка

```bash
kubectl get nodes polydev-desktop -o jsonpath='{.status.allocatable.nvidia\.com/gpu}'
```

**Ожидаемый результат:** `4` (было `1`).

Проверить labels:

```bash
kubectl describe node polydev-desktop | grep -A10 "Allocated resources"
```

---

## Использование Time-Sliced GPU

### Pod с виртуальным GPU

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: ml-inference
spec:
  runtimeClassName: nvidia
  containers:
  - name: inference
    image: your-ml-image
    resources:
      limits:
        nvidia.com/gpu: 1    # Теперь это 1/4 GPU (time-slice)
```

**Важно:** `nvidia.com/gpu: 1` теперь означает "один time-slice", а не "весь GPU".

### Запуск нескольких подов

```bash
# Теперь можно запустить 4 пода с GPU
kubectl apply -f deployment-1.yaml  # nvidia.com/gpu: 1
kubectl apply -f deployment-2.yaml  # nvidia.com/gpu: 1
kubectl apply -f deployment-3.yaml  # nvidia.com/gpu: 1
kubectl apply -f deployment-4.yaml  # nvidia.com/gpu: 1
# Все 4 запустятся!
```

---

## Мониторинг

### Проверка использования GPU

На ноде:

```bash
nvidia-smi
```

Ожидаемый вывод при нескольких подах:

```
+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI        PID   Type   Process name                        GPU Memory Usage |
|        ID   ID                                                                          |
|=========================================================================================|
|    0   N/A  N/A     12345      C   /usr/bin/python3 (YOLO)                    4096MiB  |
|    0   N/A  N/A     12346      C   /usr/bin/python3 (RIFE)                    6144MiB  |
|    0   N/A  N/A     12347      C   /usr/bin/python3 (ESRGAN)                  4096MiB  |
+-----------------------------------------------------------------------------------------+
```

### Проверка из Kubernetes

```bash
# Какие поды используют GPU
kubectl get pods -A -o wide | grep polydev

# Allocatable ресурсы
kubectl describe node polydev-desktop | grep -A5 "Allocated resources"
```

---

## Troubleshooting

### "Insufficient nvidia.com/gpu" после настройки

1. Проверить что ConfigMap создан:
   ```bash
   kubectl get configmap nvidia-device-plugin-config -n kube-system
   ```

2. Проверить логи Device Plugin:
   ```bash
   kubectl logs -n kube-system -l name=nvidia-device-plugin-ds
   ```

3. Убедиться что под перезапустился:
   ```bash
   kubectl get pods -n kube-system -l name=nvidia-device-plugin-ds
   ```

### GPU показывает 1 вместо 4

Device Plugin не подхватил конфиг:

```bash
# Проверить что volume примонтирован
kubectl describe pod -n kube-system -l name=nvidia-device-plugin-ds | grep -A5 Mounts

# Принудительно удалить и пересоздать под
kubectl delete pod -n kube-system -l name=nvidia-device-plugin-ds
```

### OOM (Out of Memory) на GPU

Time-slicing не изолирует память. Если поды суммарно превышают 48 GB:

```
RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB...
```

**Решение:**
- Уменьшить batch size в приложениях
- Уменьшить `replicas` в ConfigMap
- Не запускать memory-hungry задачи одновременно

---

## Откат к эксклюзивному режиму

Если time-slicing создаёт проблемы:

```bash
# Удалить ConfigMap
kubectl delete configmap nvidia-device-plugin-config -n kube-system

# Убрать аргумент из Device Plugin
kubectl patch daemonset nvidia-device-plugin-daemonset -n kube-system \
    --type='json' \
    -p='[{"op": "remove", "path": "/spec/template/spec/containers/0/args"}]'

# Перезапустить
kubectl rollout restart daemonset nvidia-device-plugin-daemonset -n kube-system
```

GPU снова будет показывать `1`.

---

## Версии компонентов

| Компонент | Минимальная версия | Наша версия |
|-----------|-------------------|-------------|
| NVIDIA Device Plugin | v0.12.0 | v0.17.0 |
| NVIDIA Driver | 450.80.02 | 555.52.04 |
| GPU Architecture | Pascal (2016) | Ampere (2020) |

---

## См. также

- [[K3s - GPU Support]] — базовая настройка GPU
- [[polydev-desktop]] — спецификации GPU ноды
- [[K3s - Troubleshooting]]
- [NVIDIA Time-Slicing Docs](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/gpu-sharing.html)
- [NVIDIA Device Plugin](https://github.com/NVIDIA/k8s-device-plugin)

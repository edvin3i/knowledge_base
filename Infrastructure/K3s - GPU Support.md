---
tags:
  - kubernetes
  - infrastructure
  - homelab
  - gpu
  - nvidia
created: 2026-01-19
updated: 2026-01-19
---

# K3s - GPU Support

Настройка поддержки NVIDIA GPU в [[K3s]] кластере.

## Теория: Как GPU работает в Kubernetes

### Архитектура GPU в контейнерах

```
┌─────────────────────────────────────────────────────────────────┐
│                        Kubernetes Pod                            │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                     Container                            │    │
│  │   Application (PyTorch, TensorFlow, CUDA app)           │    │
│  │              ↓                                           │    │
│  │   CUDA Libraries (/usr/local/cuda)                      │    │
│  └──────────────────────────┬──────────────────────────────┘    │
└─────────────────────────────┼───────────────────────────────────┘
                              │ (mount)
┌─────────────────────────────┼───────────────────────────────────┐
│  nvidia-container-runtime   │                                    │
│  ┌──────────────────────────┴──────────────────────────────┐    │
│  │  Монтирует в контейнер:                                  │    │
│  │  - /dev/nvidia* (GPU устройства)                        │    │
│  │  - libnvidia-*.so (драйверы)                            │    │
│  │  - nvidia-smi и утилиты                                 │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────┼───────────────────────────────────┐
│             Host OS         │                                    │
│  ┌──────────────────────────┴──────────────────────────────┐    │
│  │  NVIDIA Kernel Driver                                    │    │
│  │  (nvidia.ko, nvidia-uvm.ko)                             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              ↓                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Hardware: NVIDIA GPU                        │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Компоненты стека

| Компонент | Уровень | Назначение |
|-----------|---------|------------|
| **NVIDIA Driver** | Kernel | Взаимодействие с железом GPU |
| **nvidia-container-toolkit** | Container Runtime | Монтирует GPU в контейнеры |
| **RuntimeClass** | Kubernetes | Указывает какой runtime использовать |
| **Device Plugin** | Kubernetes | Сообщает K8s о доступных GPU |

### Device Plugin — как Kubernetes узнаёт о GPU

Kubernetes не знает о GPU напрямую. **Device Plugin** — механизм расширения:

```
┌─────────────────┐     gRPC     ┌─────────────────┐
│  nvidia-device- │◄────────────►│     kubelet     │
│     plugin      │              │                 │
└────────┬────────┘              └────────┬────────┘
         │                                │
   nvidia-smi                    Allocates GPU
   (обнаружение)                 to Pod
```

Device Plugin:
1. Обнаруживает GPU через nvidia-smi
2. Регистрируется в kubelet через Unix socket
3. Сообщает: "есть 1 ресурс nvidia.com/gpu"
4. kubelet добавляет в `.status.allocatable`

### RuntimeClass — зачем нужен

По умолчанию containerd использует **runc** — стандартный runtime без GPU.

**nvidia runtime** = runc + nvidia-container-runtime hook.

RuntimeClass говорит Kubernetes: "для этого пода используй nvidia runtime".

```yaml
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: nvidia        # имя для ссылки из Pod
handler: nvidia       # имя runtime в containerd
```

---

## Требования

- NVIDIA GPU (в нашем случае [[polydev-desktop|RTX A6000]])
- Установленные NVIDIA драйверы
- nvidia-container-toolkit

## Шаг 1: Установка K3s Agent на GPU машину

### Получение токена

На control-plane ноде:

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```

**Путь `/var/lib/rancher/k3s/server/node-token`** — файл с bootstrap токеном K3s. Создаётся при инициализации кластера.

### Установка агента

На GPU машине:

```bash
curl -sfL https://get.k3s.io | K3S_URL=https://192.168.20.225:6443 \
    K3S_TOKEN=<TOKEN> sh -
```

**Разбор переменных:**

| Переменная | Назначение |
|------------|------------|
| `K3S_URL` | Адрес API server (VIP нашего кластера) |
| `K3S_TOKEN` | Токен авторизации для присоединения |

Без `server` в аргументах — установится **agent** (worker нода).

### Проверка

```bash
kubectl get nodes
```

Новая нода должна появиться в списке со статусом `Ready`.

## Шаг 2: Проверка NVIDIA драйверов

```bash
nvidia-smi
```

**nvidia-smi** (System Management Interface) — утилита для мониторинга GPU.

Ожидаемый вывод:
```
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 555.52.04              Driver Version: 555.52.04      CUDA Version: 12.5     |
|-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
|   0  NVIDIA RTX A6000               Off |   00000000:01:00.0 Off |                  Off |
+-----------------------------------------+------------------------+----------------------+
```

**Важные поля:**

| Поле | Значение |
|------|----------|
| Driver Version | Версия kernel драйвера |
| CUDA Version | Максимальная поддерживаемая версия CUDA |
| Persistence-M | Persistence Mode (держать драйвер загруженным) |
| ECC | Error Correcting Code (для datacenter GPU) |

## Шаг 3: Установка nvidia-container-toolkit

### Проверка установки

```bash
dpkg -l | grep nvidia-container
```

**dpkg -l** — список установленных пакетов.
**grep** — фильтрация по паттерну.

### Если не установлен

```bash
# Добавить репозиторий NVIDIA
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
    sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
```

**Разбор по командам:**

| Команда | Объяснение |
|---------|------------|
| `curl -fsSL ... \| gpg --dearmor` | Скачать GPG ключ и конвертировать в бинарный формат |
| `-o /usr/share/keyrings/...` | Сохранить ключ для проверки подписи пакетов |
| `sed 's#...#...#g'` | Замена текста (добавляем путь к ключу) |
| `tee` | Записать в файл с sudo правами |
| `/etc/apt/sources.list.d/` | Директория для дополнительных репозиториев |

**GPG ключи** — криптографическая проверка что пакеты действительно от NVIDIA.

## Шаг 4: Проверка конфигурации containerd

K3s автоматически обнаруживает nvidia-container-toolkit и добавляет конфигурацию.

```bash
sudo cat /var/lib/rancher/k3s/agent/etc/containerd/config.toml
```

**containerd** — container runtime, используемый K3s (замена Docker).

Должен содержать секцию:

```toml
[plugins.'io.containerd.cri.v1.runtime'.containerd.runtimes.'nvidia']
  runtime_type = "io.containerd.runc.v2"

[plugins.'io.containerd.cri.v1.runtime'.containerd.runtimes.'nvidia'.options]
  BinaryName = "/usr/bin/nvidia-container-runtime"
  SystemdCgroup = true
```

**Разбор TOML:**

| Ключ | Значение |
|------|----------|
| `runtimes.'nvidia'` | Регистрация runtime с именем "nvidia" |
| `runtime_type` | Базовый тип (runc v2 с OCI hooks) |
| `BinaryName` | Путь к nvidia-container-runtime |
| `SystemdCgroup` | Использовать systemd для управления cgroups |

### Если секция отсутствует

> **Примечание:** nvidia-ctk 1.15.0 не поддерживает containerd config version 3.
> K3s 1.34+ автоматически добавляет конфигурацию при обнаружении toolkit.

Попробовать вручную (если версия nvidia-ctk >= 1.16):

```bash
sudo nvidia-ctk runtime configure --runtime=containerd \
    --config=/var/lib/rancher/k3s/agent/etc/containerd/config.toml
sudo systemctl restart k3s-agent
```

**nvidia-ctk** — CLI утилита nvidia-container-toolkit.
- `runtime configure` — автоматическая настройка container runtime
- `--runtime=containerd` — тип runtime
- `--config=...` — путь к конфигу

## Шаг 5: Установка NVIDIA Device Plugin

```bash
kubectl apply -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.17.0/deployments/static/nvidia-device-plugin.yml
```

**kubectl apply -f** — применить манифест (создать/обновить ресурсы).

**Разбор URL:**
- `raw.githubusercontent.com` — сырой файл из GitHub
- `v0.17.0` — версия релиза
- `nvidia-device-plugin.yml` — манифест DaemonSet

**DaemonSet** — запускает по одному поду на каждой ноде. Device Plugin должен работать на всех GPU нодах.

## Шаг 6: Создание RuntimeClass

```bash
kubectl create -f - <<'EOF'
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: nvidia
handler: nvidia
EOF
```

**Разбор синтаксиса:**

| Элемент | Объяснение |
|---------|------------|
| `kubectl create -f -` | Создать ресурс, читая из stdin |
| `<<'EOF'` | Here-document (многострочный ввод до EOF) |
| Кавычки `'EOF'` | Отключить интерполяцию переменных |
| `apiVersion: node.k8s.io/v1` | API группа для RuntimeClass |
| `kind: RuntimeClass` | Тип ресурса |
| `handler: nvidia` | Должен совпадать с именем в containerd config |

## Шаг 7: Настройка Device Plugin для nvidia runtime

Device plugin должен использовать nvidia runtime для обнаружения GPU:

```bash
kubectl patch daemonset nvidia-device-plugin-daemonset -n kube-system \
    --type='json' \
    -p='[{"op": "add", "path": "/spec/template/spec/runtimeClassName", "value": "nvidia"}]'
```

**Разбор kubectl patch:**

| Элемент | Объяснение |
|---------|------------|
| `patch` | Частичное обновление ресурса |
| `daemonset` | Тип ресурса |
| `-n kube-system` | Namespace |
| `--type='json'` | JSON Patch (RFC 6902) |
| `op: add` | Операция — добавить поле |
| `path` | JSONPath к полю в манифесте |
| `value` | Новое значение |

**Зачем это нужно:**
Device Plugin запускается в контейнере. Чтобы он мог обнаружить GPU, ему нужен доступ к nvidia runtime.

## Шаг 8: Добавление меток GPU ноде

```bash
kubectl label nodes polydev-desktop node-role.kubernetes.io/gpu=true
kubectl label nodes polydev-desktop nvidia.com/gpu=present
```

**Labels (метки)** — key-value пары для организации и выборки ресурсов.

| Label | Назначение |
|-------|------------|
| `node-role.kubernetes.io/gpu=true` | Стандартная метка роли (отображается в `kubectl get nodes`) |
| `nvidia.com/gpu=present` | Кастомная метка для nodeSelector в подах |

**Зачем нужны:**
```yaml
# В Pod можно указать
nodeSelector:
  nvidia.com/gpu: present
```

Scheduler запустит под только на нодах с этой меткой.

---

## Проверка

### Статус device plugin

```bash
kubectl get pods -n kube-system -l name=nvidia-device-plugin-ds -o wide
```

| Флаг | Объяснение |
|------|------------|
| `-l name=...` | Label selector — только поды с этой меткой |
| `-o wide` | Расширенный вывод (показывает ноду) |

### Логи device plugin на GPU ноде

```bash
kubectl logs -n kube-system -l name=nvidia-device-plugin-ds \
    --field-selector spec.nodeName=polydev-desktop
```

| Флаг | Объяснение |
|------|------------|
| `logs` | Получить логи пода |
| `--field-selector` | Фильтр по полям объекта (не labels) |
| `spec.nodeName` | Имя ноды, на которой запущен под |

Успешный вывод:

```
I0119 18:46:37.712296       1 server.go:195] Starting GRPC server for 'nvidia.com/gpu'
I0119 18:46:37.714122       1 server.go:146] Registered device plugin for 'nvidia.com/gpu' with Kubelet
```

### GPU ресурсы на ноде

```bash
kubectl get nodes polydev-desktop -o jsonpath='{.status.allocatable}' | jq .
```

| Элемент | Объяснение |
|---------|------------|
| `-o jsonpath='{...}'` | Вывести только указанное поле в JSON формате |
| `.status.allocatable` | Ресурсы, доступные для scheduling |
| `\| jq .` | Pretty-print JSON |

**jq** — CLI утилита для работы с JSON. Точка `.` = весь документ.

Ожидаемый вывод:

```json
{
  "cpu": "24",
  "memory": "65666352Ki",
  "nvidia.com/gpu": "1",
  ...
}
```

**`nvidia.com/gpu: 1`** — GPU успешно обнаружен и доступен.

### Тестовый pod с GPU

```bash
kubectl run gpu-test --rm -it --restart=Never \
    --image=nvidia/cuda:12.5.0-base-ubuntu22.04 \
    --overrides='{"spec":{"runtimeClassName":"nvidia","resources":{"limits":{"nvidia.com/gpu":"1"}}}}' \
    -- nvidia-smi
```

**Разбор:**

| Флаг | Объяснение |
|------|------------|
| `run` | Создать и запустить под |
| `--rm` | Удалить после завершения |
| `-it` | Interactive + TTY (для вывода в терминал) |
| `--restart=Never` | Не перезапускать (одноразовый под) |
| `--image=...` | Docker образ |
| `--overrides=...` | JSON для переопределения spec |
| `-- nvidia-smi` | Команда для выполнения в контейнере |

**overrides JSON:**
```json
{
  "spec": {
    "runtimeClassName": "nvidia",    // Использовать nvidia runtime
    "resources": {
      "limits": {
        "nvidia.com/gpu": "1"        // Запросить 1 GPU
      }
    }
  }
}
```

---

## Troubleshooting

### "Incompatible strategy detected auto"

Device plugin не видит GPU.

**Решение:** добавить `runtimeClassName: nvidia` в DaemonSet (Шаг 7).

### "No devices found"

1. Проверить nvidia-smi на хосте
2. Проверить конфигурацию containerd
3. Перезапустить k3s-agent: `sudo systemctl restart k3s-agent`

### GPU не показывается в allocatable

1. Проверить логи device plugin
2. Убедиться что RuntimeClass создан
3. Проверить что device plugin использует nvidia runtime

---

## Использование GPU в workloads

### Pod с GPU

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: gpu-pod
spec:
  runtimeClassName: nvidia          # ОБЯЗАТЕЛЬНО для GPU
  containers:
  - name: cuda-container
    image: nvidia/cuda:12.5.0-base-ubuntu22.04
    resources:
      limits:
        nvidia.com/gpu: 1           # Запросить 1 GPU
    command: ["nvidia-smi", "-l", "10"]
  nodeSelector:
    nvidia.com/gpu: present         # Только на GPU нодах
```

**Ключевые поля:**

| Поле | Назначение |
|------|------------|
| `runtimeClassName` | Какой container runtime использовать |
| `resources.limits` | Лимиты ресурсов (GPU — лимит = запрос) |
| `nvidia.com/gpu` | Extended resource для GPU |
| `nodeSelector` | На каких нодах запускать |

### Deployment с GPU

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ml-worker
spec:
  replicas: 1                       # Обычно 1 replica = 1 GPU
  selector:
    matchLabels:
      app: ml-worker
  template:
    metadata:
      labels:
        app: ml-worker
    spec:
      runtimeClassName: nvidia
      nodeSelector:
        nvidia.com/gpu: present
      containers:
      - name: worker
        image: your-ml-image
        resources:
          limits:
            nvidia.com/gpu: 1
```

> **Важно:** `replicas` ограничено количеством GPU. Если 1 GPU — максимум 1 реплика с GPU.

---

## Версии компонентов

| Компонент | Версия | Проверка |
|-----------|--------|----------|
| K3s | v1.34.3+k3s1 | `k3s --version` |
| containerd | 2.1.5-k3s1 | `k3s ctr version` |
| NVIDIA Driver | 555.52.04 | `nvidia-smi` |
| CUDA | 12.5 | `nvidia-smi` |
| nvidia-container-toolkit | 1.15.0 | `dpkg -l \| grep nvidia-container` |
| nvidia-device-plugin | v0.17.0 | `kubectl get ds -n kube-system` |

---

## Следующие шаги

После базовой настройки GPU можно:

- [[K3s - GPU Sharing]] — разделить GPU между несколькими подами (Time-Slicing)
- Настроить мониторинг GPU через DCGM Exporter
- Интегрировать с [[ClearML]] для ML workloads

---

## См. также

- [[K3s]]
- [[K3s - GPU Sharing]] — Time-Slicing, MPS, MIG
- [[K3s - Troubleshooting]]
- [[polydev-desktop]]
- [[K3s - Установка HA]]
- [NVIDIA Device Plugin](https://github.com/NVIDIA/k8s-device-plugin)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/)

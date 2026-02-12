---
tags:
  - kubernetes
  - storage
  - infrastructure
created: 2026-01-19
updated: 2026-01-22
---

# Longhorn

Распределённое блочное хранилище для [[Kubernetes]]. Установлен в [[K3s]] кластере.

## Теория: Storage в Kubernetes

### Проблема: Контейнеры эфемерны

Контейнеры не хранят состояние — при перезапуске все данные теряются. Решение — **Persistent Volumes**.

```
┌─────────────────────────────────────────────────────────────────┐
│                     Kubernetes Storage Stack                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────────────┐                                          │
│   │       Pod        │  Использует volume                       │
│   └────────┬─────────┘                                          │
│            │ volumeMounts                                        │
│            ▼                                                     │
│   ┌──────────────────┐                                          │
│   │       PVC        │  Запрос на storage (что нужно)           │
│   │ PersistentVolume │                                          │
│   │     Claim        │  "Мне нужно 10Gi с RWO"                  │
│   └────────┬─────────┘                                          │
│            │ binding                                             │
│            ▼                                                     │
│   ┌──────────────────┐                                          │
│   │       PV         │  Реальный volume (что есть)              │
│   │ PersistentVolume │                                          │
│   │                  │  "Есть 10Gi на node-1"                   │
│   └────────┬─────────┘                                          │
│            │ provisioner                                         │
│            ▼                                                     │
│   ┌──────────────────┐                                          │
│   │  StorageClass    │  Как создавать PV                        │
│   │                  │                                          │
│   │  provisioner:    │  "Использовать Longhorn"                 │
│   │  driver.longhorn.io │                                          │
│   └────────┬─────────┘                                          │
│            │                                                     │
│            ▼                                                     │
│   ┌──────────────────┐                                          │
│   │    Longhorn      │  Реальное хранилище                      │
│   │    (CSI Driver)  │                                          │
│   └──────────────────┘                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Access Modes — режимы доступа

| Mode | Сокращение | Описание |
|------|------------|----------|
| ReadWriteOnce | RWO | Одна **нода** может монтировать для чтения/записи |
| ReadOnlyMany | ROX | Много нод могут монтировать только для чтения |
| ReadWriteMany | RWX | Много нод могут монтировать для чтения/записи |
| ReadWriteOncePod | RWOP | Один **под** может читать/писать (K8s 1.22+) |

> **Важно:** RWO ограничивает доступ **одной нодой**, а не одним подом. Несколько подов на одной ноде могут одновременно использовать RWO volume. Для настоящей single-pod изоляции используйте RWOP.

**Longhorn** поддерживает RWO (основной) и RWX (через NFS).

### Dynamic Provisioning

**Без dynamic provisioning:**
1. Админ создаёт PV вручную
2. Пользователь создаёт PVC
3. Kubernetes связывает PVC с подходящим PV

**С dynamic provisioning (Longhorn):**
1. Пользователь создаёт PVC
2. StorageClass автоматически создаёт PV
3. Kubernetes связывает их

### Как работает Longhorn

```
┌─────────────────────────────────────────────────────────────────┐
│                      Longhorn Architecture                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│    Node 1 (где запущен Pod)       Node 2           Node 3       │
│   ┌─────────────────────────┐   ┌───────┐        ┌───────┐     │
│   │  ┌───────┐   ┌───────┐ │   │Replica│        │Replica│     │
│   │  │  Pod  │   │Engine │ │   │  (2)  │        │  (3)  │     │
│   │  │       │◄─►│(Head) │─┼──►│       │        │       │     │
│   │  └───────┘   └───┬───┘ │   └───────┘        └───────┘     │
│   │    iSCSI         │     │       ▲                  ▲        │
│   │   (локально)     │     │       │    TCP sync      │        │
│   │              ┌───▼───┐ │       │   (Longhorn)     │        │
│   │              │Replica│─┼───────┴──────────────────┘        │
│   │              │  (1)  │ │                                    │
│   │              └───────┘ │                                    │
│   └─────────────────────────┘                                   │
│                                                                  │
│   Ключевые моменты:                                             │
│   • Engine ВСЕГДА на той же ноде, что и Pod                     │
│   • iSCSI — локальное соединение (Engine → Pod на одной ноде)   │
│   • Репликация между нодами — TCP (не iSCSI)                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Ключевые компоненты:**

| Компонент | Назначение |
|-----------|------------|
| **longhorn-manager** | Управление volumes, nodes, replicas |
| **longhorn-driver** | CSI driver для Kubernetes |
| **longhorn-engine** | Контроллер volume (head) |
| **longhorn-replica** | Хранение данных (реплики) |
| **longhorn-ui** | Веб-интерфейс |

**Репликация:**
- Данные копируются на несколько нод (по умолчанию 3, у нас 2)
- При падении ноды — данные не теряются
- Longhorn автоматически восстанавливает реплики

---

## Статус

| Параметр | Значение |
|----------|----------|
| **Версия** | 1.10.1 |
| **Namespace** | `longhorn-system` |
| **StorageClass** | `longhorn` (default) |
| **UI** | http://192.168.20.239 |

## Ноды хранилища

| Нода | Статус | Schedulable |
|------|--------|-------------|
| [[polynode-1]] | Ready | Yes |
| [[polynode-2]] | Ready | Yes |
| [[polynode-3]] | Ready | Yes |
| [[polydev-desktop]] | Ready | Yes |

---

## Установка

### Зависимости

На **каждой** ноде:

```bash
# Debian/Ubuntu
sudo apt update && sudo apt install -y open-iscsi
sudo systemctl enable --now iscsid
```

**Разбор:**

| Элемент | Объяснение |
|---------|------------|
| `open-iscsi` | iSCSI initiator — протокол для подключения к storage |
| `enable --now` | Включить автозапуск И запустить сейчас |
| `iscsid` | Daemon для iSCSI соединений |

**Зачем iSCSI?**
Longhorn использует iSCSI для подключения volumes к подам. Это стандартный протокол storage-over-network.

### Helm установка

```bash
# Добавить репозиторий
helm repo add longhorn https://charts.longhorn.io
helm repo update
```

**Разбор Helm:**

| Команда | Объяснение |
|---------|------------|
| `helm repo add` | Добавить репозиторий чартов |
| `longhorn` | Локальное имя репозитория |
| `https://...` | URL репозитория |
| `helm repo update` | Обновить индекс (список доступных чартов) |

```bash
# Установить (проверь актуальную версию на charts.longhorn.io)
helm install longhorn longhorn/longhorn \
  --namespace longhorn-system \
  --create-namespace \
  --version 1.10.1 \
  --set defaultSettings.defaultDataPath="/var/lib/longhorn" \
  --set defaultSettings.defaultReplicaCount=2
```

**Разбор команды:**

| Элемент | Объяснение |
|---------|------------|
| `helm install` | Установить чарт |
| `longhorn` (первый) | Имя релиза (для управления) |
| `longhorn/longhorn` | Репозиторий/чарт |
| `--namespace` | В какой namespace установить |
| `--create-namespace` | Создать namespace если не существует |
| `--version` | Конкретная версия чарта |
| `--set` | Переопределить значения из values.yaml |

**Параметры `--set`:**

| Параметр | Значение | Почему |
|----------|----------|--------|
| `defaultDataPath` | `/var/lib/longhorn` | Где хранить данные на нодах |
| `defaultReplicaCount` | `2` | 2 реплики (у нас 4 ноды, 3 достаточно для отказоустойчивости) |

### Проверка

```bash
# Все поды должны быть Running
kubectl -n longhorn-system get pods
```

Ожидаемые поды:
- `longhorn-manager-xxxxx` (на каждой ноде)
- `longhorn-driver-deployer-xxxxx`
- `longhorn-ui-xxxxx`
- `csi-attacher`, `csi-provisioner`, `csi-resizer`, `csi-snapshotter`
- `engine-image-xxxxx`
- `instance-manager-xxxxx`

```bash
# Ноды зарегистрированы
kubectl -n longhorn-system get nodes.longhorn.io
```

**`nodes.longhorn.io`** — Custom Resource Definition (CRD). Longhorn создаёт свой тип ресурса для представления нод хранилища.

```bash
# StorageClass создан
kubectl get storageclass
```

---

## StorageClass

### Теория: Что такое StorageClass

StorageClass — шаблон для создания PV. Определяет:
- **provisioner** — кто создаёт volumes
- **parameters** — настройки (репликация, тип диска)
- **reclaimPolicy** — что делать при удалении PVC

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: longhorn
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"  # Default SC
provisioner: driver.longhorn.io        # CSI driver
allowVolumeExpansion: true             # Можно увеличивать размер
reclaimPolicy: Delete                  # Удалять PV при удалении PVC
volumeBindingMode: Immediate           # Создавать PV сразу
parameters:
  numberOfReplicas: "2"                # Количество реплик
  staleReplicaTimeout: "2880"          # Таймаут для stale реплик
```

**reclaimPolicy:**

| Policy | Поведение |
|--------|-----------|
| Delete | PV удаляется вместе с PVC (для dynamic provisioning) |
| Retain | PV сохраняется (для важных данных) |

### После установки создаются

- `longhorn` — динамический provisioner (default)
- `longhorn-static` — для статических PV

### Убрать default с local-path

K3s по умолчанию ставит `local-path` как default. Два default — ошибка.

```bash
kubectl patch storageclass local-path -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"false"}}}'
```

**Разбор kubectl patch:**

| Элемент | Объяснение |
|---------|------------|
| `patch` | Частичное обновление |
| `storageclass` | Тип ресурса |
| `local-path` | Имя ресурса |
| `-p '...'` | JSON patch payload |
| `annotations` | Метаданные (не labels!) |

---

## Использование

### Создание PVC

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: my-pvc
spec:
  accessModes:
    - ReadWriteOnce        # Режим доступа
  resources:
    requests:
      storage: 10Gi        # Запрошенный размер
  # storageClassName: longhorn  # Не нужно если default
```

**Разбор полей:**

| Поле | Объяснение |
|------|------------|
| `accessModes` | Как pods могут использовать volume |
| `ReadWriteOnce` | Один pod может читать/писать |
| `resources.requests.storage` | Сколько места нужно |
| `storageClassName` | Какой SC использовать (опционально если default) |

### Использование в Pod

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: my-pod
spec:
  containers:
  - name: app
    image: nginx
    volumeMounts:
    - name: data
      mountPath: /data          # Куда монтировать в контейнере
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: my-pvc         # Имя PVC
```

**Жизненный цикл:**
1. Pod создаётся
2. Kubernetes видит volume с PVC
3. Longhorn подключает volume к ноде через iSCSI
4. kubelet монтирует в контейнер
5. Pod запускается с данными

---

## UI Dashboard

Longhorn имеет веб-интерфейс для мониторинга и управления.

### Доступ

**Через LoadBalancer (рекомендуется):**

http://192.168.20.239

**Через port-forward (альтернатива):**

```bash
kubectl -n longhorn-system port-forward svc/longhorn-frontend 8080:80
# Открыть http://localhost:8080
```

**Что показывает UI:**
- Состояние нод
- Volumes и их реплики
- Snapshots
- Backups
- Settings

---

## Добавление дополнительных дисков

Longhorn может использовать несколько дисков на одной ноде.

### Подготовка

На ноде с дополнительным диском:

```bash
# Создать директорию для Longhorn
sudo mkdir -p /mnt/longhorn
sudo chmod 700 /mnt/longhorn
```

**Важно:** Диск должен быть смонтирован постоянно (в `/etc/fstab`).

### Добавление через UI

```bash
kubectl -n longhorn-system port-forward svc/longhorn-frontend 9080:80
```

Открыть http://localhost:9080:
1. **Node** → выбрать ноду
2. **Edit Node and Disks**
3. **Add Disk**:
   - Path: `/mnt/longhorn`
   - Storage Reserved: `0`
4. **Save**

### Добавление через kubectl

```bash
kubectl -n longhorn-system edit nodes.longhorn.io <node-name>
```

Добавить в `spec.disks`:

```yaml
spec:
  disks:
    default-disk-xxxxx:
      allowScheduling: true
      path: /var/lib/longhorn
      storageReserved: 0
    mnt-disk:                      # новый диск
      allowScheduling: true
      evictionRequested: false
      path: /mnt/longhorn
      storageReserved: 0
      tags: []
```

### Наш кластер

| Нода | Диски | Tags |
|------|-------|------|
| polynode-1/2/3 | `/var/lib/longhorn` | — |
| [[polydev-desktop]] | `/var/lib/longhorn`, `/mnt/longhorn` | `large-storage` на `/mnt/longhorn` |

---

## Disk Tags и Node/Disk Selectors

### Теория

Longhorn позволяет привязывать реплики volumes к конкретным нодам и дискам через **tags** и **selectors**:

- **Disk Tags** — метки на дисках (например, `large-storage`, `ssd`, `hdd`)
- **diskSelector** — volume будет размещать реплики только на дисках с указанными тегами
- **nodeSelector** — volume будет размещать реплики только на указанных нодах

Это полезно когда:
- Нужно разместить большой volume на конкретном диске с достаточным местом
- Нужно разделить SSD и HDD storage
- Нужно изолировать workloads на определённых нодах

### Настройка disk tag

**Через UI:** Longhorn UI → Node → выбрать ноду → Edit Node and Disks → выбрать диск → Tags → добавить тег → Save

**Через kubectl:**

```bash
kubectl -n longhorn-system edit nodes.longhorn.io <node-name>
```

Добавить `tags` в нужный диск:

```yaml
spec:
  disks:
    mnt-disk:
      allowScheduling: true
      path: /mnt/longhorn
      storageReserved: 0
      tags:
        - large-storage
```

### Привязка volume к ноде/диску

```bash
# Привязать volume к ноде polydev-desktop и диску с тегом large-storage
kubectl -n longhorn-system patch volumes.longhorn.io <volume-name> \
  --type=merge \
  -p '{"spec":{"nodeSelector":["polydev-desktop"],"diskSelector":["large-storage"]}}'
```

**Параметры:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `nodeSelector` | `[]string` | Список нод, на которых могут быть реплики |
| `diskSelector` | `[]string` | Список disk tags, реплики только на дисках с этими тегами |

> **Важно:** Если задан `diskSelector`, но на ноде нет диска с нужным тегом — реплика на эту ноду не попадёт, даже если нода указана в `nodeSelector`.

### Наш кейс: MinIO на polydev-desktop

MinIO PVC (500Gi) привязан к polydev-desktop через selectors:

```
nodeSelector: ["polydev-desktop"]
diskSelector: ["large-storage"]
```

Это гарантирует, что данные MinIO хранятся на большом диске `/mnt/longhorn` (2TB), а не на маленьких дисках polynode-1/2/3 (256Gi).

---

## Настройки

Основные параметры в `defaultSettings`:

| Параметр | Описание | Наше значение |
|----------|----------|---------------|
| `defaultDataPath` | Путь хранения данных | `/var/lib/longhorn` |
| `defaultReplicaCount` | Кол-во реплик volume | `2` |
| `backupTarget` | S3/NFS для бэкапов | не настроен |
| `storageOverProvisioningPercentage` | Overprovisioning | 200% |
| `storageMinimalAvailablePercentage` | Минимум свободного места | 25% |

### Изменение настроек

Через UI или kubectl:

```bash
kubectl -n longhorn-system edit settings.longhorn.io <setting-name>
```

---

## Troubleshooting

### Pods в CrashLoopBackOff

**Симптом:** `longhorn-manager` не стартует на некоторых нодах.

**Причина:** Firewall блокирует pod-to-pod трафик.

**Диагностика:**
```bash
kubectl -n longhorn-system logs -l app=longhorn-manager --all-containers
```

**Решение:** Открыть порты для K3s сетей. См. [[K3s - Troubleshooting#UFW блокирует pod-to-pod трафик]].

### Нода не появляется в Longhorn

**Проверить:**

1. **iscsid запущен:**
```bash
systemctl status iscsid
```

2. **Longhorn manager Running на ноде:**
```bash
kubectl -n longhorn-system get pods -o wide | grep manager
```

3. **Firewall не блокирует:**
```bash
sudo ufw status  # На Ubuntu
```

### Volume stuck в Attaching/Detaching

```bash
# Логи engine
kubectl -n longhorn-system logs -l longhorn.io/component=engine-manager

# Force detach через UI или:
kubectl -n longhorn-system patch volumes.longhorn.io <vol-name> \
  --type merge -p '{"spec":{"nodeID":""}}'
```

### Volume Degraded: ReplicaSchedulingFailure

**Симптом:** Volume показывает статус `degraded` в UI Longhorn или в kubectl.

**Причина:** Longhorn не может разместить все реплики — недостаточно места на нодах.

#### Теория: Как Longhorn планирует реплики

Longhorn при создании volume размещает реплики на **разные ноды** (anti-affinity) для отказоустойчивости. Каждая нода имеет лимиты:

```
Allocated (занято) + New Replica ≤ Maximum (лимит ноды)
```

Если на всех подходящих нодах `Allocated + ReplicaSize > Maximum`, реплика остаётся в статусе `stopped` без привязки к ноде.

#### Диагностика

```bash
# 1. Проверить статус volume
kubectl get volumes.longhorn.io -n longhorn-system <volume-name> -o yaml | grep -A5 status

# Искать:
#   robustness: degraded
#   message: insufficient storage
#   reason: ReplicaSchedulingFailure

# 2. Проверить реплики
kubectl get replicas.longhorn.io -n longhorn-system \
  -l longhornvolume=<volume-name> -o wide

# Пример вывода:
# NAME          STATE     NODE              ← stopped реплика без ноды
# xxx-r-abc123  running   polydev-desktop
# xxx-r-def456  running   polynode-1
# xxx-r-ghi789  stopped                     ← проблемная реплика

# 3. Проверить capacity нод
kubectl get nodes.longhorn.io -n longhorn-system -o json | \
  jq -r '.items[] | "\(.metadata.name): allocated=\(.status.diskStatus | to_entries[0].value.storageScheduled/1024/1024/1024 | floor)Gi max=\(.status.diskStatus | to_entries[0].value.storageMaximum/1024/1024/1024 | floor)Gi"'
```

#### Пример реальной проблемы

Volume MinIO (100Gi) требовал 3 реплики:

| Нода | Allocated | Max | Может вместить 100Gi? |
|------|-----------|-----|----------------------|
| polydev-desktop | 213 Gi | 1832 Gi | ✅ Да, но уже есть реплика |
| polynode-1 | 125 Gi | 224 Gi | ✅ Да, но уже есть реплика |
| polynode-2 | 138 Gi | 224 Gi | ❌ 138+100=238 > 224 |
| polynode-3 | 138 Gi | 224 Gi | ❌ 138+100=238 > 224 |

**Вывод:** Третья реплика не может быть размещена — все свободные ноды переполнены.

#### Решения

**Вариант 1: Уменьшить количество реплик (рекомендуется для standalone workloads)**

Для приложений с одним подом (MinIO standalone, PostgreSQL) 2 реплики обеспечивают достаточную защиту:

```bash
kubectl patch volume <volume-name> \
  -n longhorn-system \
  --type=merge \
  -p '{"spec":{"numberOfReplicas":2}}'

# Longhorn автоматически удалит лишнюю stopped реплику
```

**Вариант 2: Увеличить storage over-provisioning**

Позволяет выделять больше места, чем физически есть (рискованно):

```bash
# Текущее значение
kubectl get settings.longhorn.io -n longhorn-system \
  storage-over-provisioning-percentage -o jsonpath='{.value}'

# Увеличить до 150%
kubectl patch settings.longhorn.io storage-over-provisioning-percentage \
  -n longhorn-system \
  --type=merge \
  -p '{"value":"150"}'
```

**Вариант 3: Разрешить несколько реплик на одной ноде**

Отключить anti-affinity для конкретного volume:

```bash
kubectl patch volume <volume-name> \
  -n longhorn-system \
  --type=merge \
  -p '{"spec":{"replicaSoftAntiAffinity":"true"}}'
```

⚠️ **Риск:** Если нода с двумя репликами упадёт — потеря данных возможна.

**Вариант 4: Добавить storage**

- Добавить диск на существующую ноду (см. [[#Добавление дополнительных дисков]])
- Добавить новую ноду в кластер

#### Проверка после исправления

```bash
# Статус должен стать healthy
kubectl get volumes.longhorn.io -n longhorn-system <volume-name> \
  -o jsonpath='{.status.robustness}'
# Ожидаемый вывод: healthy

# Все реплики running
kubectl get replicas.longhorn.io -n longhorn-system \
  -l longhornvolume=<volume-name>
```

---

### Нода Unschedulable (overallocation)

**Симптом:** Нода показывает красный Allocated bar и статус Unschedulable.

**Причина:** Сумма размеров реплик (Allocated) превышает доступное место (Size).

```
Allocated: 203 / 157.48 Gi  ← красный, >100%
```

**Диагностика:**
```bash
kubectl get nodes.longhorn.io -n longhorn-system
# Или UI: http://192.168.20.239 → Nodes
```

**Решения:**
1. Уменьшить количество реплик для volumes
2. Уменьшить размер PVC (требует пересоздания)
3. Добавить диск на ноду
4. Перенести реплики на ноды с большим storage (polydev-desktop)

```bash
# Уменьшить реплики volume до 1
kubectl -n longhorn-system patch volumes.longhorn.io <vol-name> \
  --type merge -p '{"spec":{"numberOfReplicas":1}}'
```

---

## Полезные команды

```bash
# Список volumes
kubectl -n longhorn-system get volumes.longhorn.io

# Детали volume
kubectl -n longhorn-system describe volumes.longhorn.io <name>

# Реплики volume
kubectl -n longhorn-system get replicas.longhorn.io -l longhornvolume=<vol-name>

# Snapshots
kubectl -n longhorn-system get snapshots.longhorn.io

# Ноды и их capacity
kubectl -n longhorn-system get nodes.longhorn.io -o wide
```

---

## См. также

- [[K3s]]
- [[K3s - Troubleshooting]]
- [[Kubernetes]]
- [[Helm]]
- [Longhorn Documentation](https://longhorn.io/docs/)
- [Longhorn Architecture](https://longhorn.io/docs/latest/concepts/)

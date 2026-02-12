---
tags:
  - kubernetes
  - linux
  - virtualization
  - containers
  - theory
created: 2026-02-12
---

# VM, Container, Pod — сущностное понимание

Три уровня изоляции: от аппаратной виртуализации до группировки процессов. Эта статья объясняет **что происходит на уровне ОС**, а не только абстракции Kubernetes.

## Содержание

- [[#Спектр изоляции]]
- [[#Виртуальная машина (VM)]]
- [[#Контейнер]]
- [[#Pod]]
- [[#Сравнительная таблица]]
- [[#Практика — команды для исследования]]

---

## Спектр изоляции

```
  Isolation ──────────────────────────────────────────────►
  Overhead  ──────────────────────────────────────────────►

  Process ──► Container ──► microVM ──► VM ──► Bare Metal
```

| | Process | Container | microVM (Firecracker) | VM | Bare Metal |
|---|---|---|---|---|---|
| **Kernel** | Host | Host | Own (minimal) | Own (full OS) | Full control |
| **FS** | Shared | Own rootfs | Own rootfs | Virtual disk | Physical |
| **Network** | Shared | Own NS | Own NS | Virtual NIC | Physical |
| **Overhead** | ~0 | ~0 | ~5 MiB | ~GiB | N/A |
| **Boot** | ~0 ms | ~50 ms | ~125 ms | ~1-2 s | N/A |

Каждый уровень добавляет **границу доверия** (trust boundary). Процесс доверяет ядру. Контейнер доверяет ядру, но ограничен в видимости. VM имеет собственное ядро, граница доверия проходит на уровне гипервизора.

---

## Виртуальная машина (VM)

### Что это на уровне хоста

VM — это **процесс гипервизора**, внутри которого работает полноценная гостевая ОС со своим ядром. Гостевые процессы **не видны** на хосте.

```
HOST (Linux)

  qemu-system-x86_64        <-- main process
  |-- vCPU 0 thread          (KVM ioctl: VMENTER/VMEXIT)
  |-- vCPU 1 thread
  |-- vCPU 2 thread
  |-- vCPU 3 thread
  |-- I/O thread (virtio-blk)
  |-- I/O thread (virtio-net)
  +-- main loop thread       (QEMU event loop)

  All threads = ONE process (same PID, different TIDs)
```

```bash
# Один процесс QEMU на каждую VM
ps aux | grep qemu
# libvirt  12345  45.2  25.0 ... qemu-system-x86_64 -name guest=myvm ...

# Потоки (vCPU threads):
ps -eLf | grep qemu
# или htop → нажать H для показа потоков
```

### Архитектура виртуализации

```
+-----------------------------------+
|  Guest OS                         |
|  [bash] [sshd] [nginx]           |  <-- NOT visible on host
|  Guest Kernel                     |
+-----------------------------------+
|  Virtual HW (virtio-net, blk...) |
+-----------------------------------+
|  QEMU-KVM process (host)         |  <-- THIS is visible on host
|  + vCPU threads                   |
+-----------------------------------+
|  KVM kernel module                |
+-----------------------------------+
|  Hardware (CPU VT-x / AMD-V)     |
+-----------------------------------+
```

### Аппаратная виртуализация: VT-x / AMD-V

Каждый vCPU thread выполняет инструкцию `VMENTER`, передавая управление гостевому коду **напрямую на процессоре**. При привилегированных операциях происходит `VMEXIT` обратно в KVM. Это аппаратная виртуализация — не эмуляция.

**Виртуализация памяти (EPT/NPT):** процессор аппаратно выполняет двухуровневую трансляцию Guest VA → Guest PA → Host PA, устраняя необходимость в shadow page tables. Это даёт до 48% прироста для memory-intensive нагрузок.

### Критерии Попека-Голдберга (1974)

Формальное определение Virtual Machine Monitor (VMM) — три свойства:

1. **Equivalence:** программа под VMM ведёт себя идентично исполнению на реальном железе
2. **Efficiency:** доминирующее подмножество инструкций исполняется напрямую на процессоре
3. **Resource Control:** VMM полностью контролирует ресурсы, ни одна программа не обойдёт его

> **Теорема:** VMM может быть построен тогда и только тогда, когда множество *sensitive instructions* является подмножеством *privileged instructions*.

**Проблема x86:** архитектура x86 не удовлетворяла этим критериям — некоторые sensitive-инструкции (`POPF`, `SGDT`) не вызывали trap. Решения до VT-x: binary translation (VMware), paravirtualization (Xen). После VT-x/AMD-V (2005-2006) — аппаратный trap-and-emulate.

### Type-1 vs Type-2 гипервизоры

```
Type-1 (Bare-Metal)           Type-2 (Hosted)

+-----+-----+-----+          +-----+-----+
| VM1 | VM2 | VM3 |          | VM1 | VM2 |
+-----+-----+-----+          +-----+-----+
|   Hypervisor    |          |  Hypervisor  |
+-----------------+          +--------------+
|    Hardware     |          |  Host OS     |
+-----------------+          +--------------+
                              |  Hardware    |
ESXi, Xen, Hyper-V           +--------------+
                              VirtualBox, QEMU
```

**KVM — гибрид:** модуль ядра (формально Type-1), но ядро Linux продолжает работать как полноценная ОС. QEMU обеспечивает эмуляцию устройств в userspace.

---

## Контейнер

### Фундаментальный инсайт

> **В ядре Linux НЕТ сущности "контейнер".** Нет syscall `create_container()`. Контейнер — это конвенция userspace, комбинирующая три механизма ядра:

```
Container = Namespaces (изоляция видимости)
          + Cgroups (лимиты ресурсов)
          + Union FS (слоёная файловая система)
```

### Контейнер vs VM — ключевое отличие

В `ps aux` на хосте **ВИДНЫ ВСЕ** процессы всех контейнеров:

```
HOST (Linux) -- ONE shared kernel

  PID 1:   systemd
  PID 100: containerd
  PID 200: nginx          <-- container A
  PID 201: nginx worker   <-- container A
  PID 300: redis-server   <-- container B
  PID 400: postgres       <-- container C

  ALL processes visible! ALL share ONE kernel!
```

Внутри контейнера nginx думает, что его PID = 1. На хосте его реальный PID = 200. Это работа **PID namespace**.

### Linux Namespaces — изоляция видимости

| Namespace | Год | Что изолирует | Пример |
|-----------|-----|---------------|--------|
| **Mount** | 2002 | Точки монтирования | Контейнер видит свой rootfs |
| **UTS** | 2006 | Hostname | `hostname` возвращает имя контейнера |
| **IPC** | 2006 | Shared memory, semaphores | Изоляция межпроцессного взаимодействия |
| **PID** | 2008 | Дерево процессов | PID начинается с 1, чужие процессы невидимы |
| **Network** | 2009 | Сетевой стек | Свой eth0, свои порты, свой IP |
| **User** | 2012 | UID/GID маппинг | root в контейнере = nobody на хосте |
| **Cgroup** | 2016 | Видимость cgroup hierarchy | Контейнер видит только свои cgroups |
| **Time** | 2020 | CLOCK_MONOTONIC, CLOCK_BOOTTIME | Для CRIU checkpoint/restore |

**Механизм:** три системных вызова:
- `clone()` с `CLONE_NEW*` — создать процесс в новых namespaces
- `unshare()` — переместить текущий процесс в новые namespaces
- `setns()` — присоединить процесс к существующему namespace

### Cgroups — ограничение ресурсов

Namespaces изолируют **видимость**, cgroups ограничивают **потребление**.

```
cgroups v2 hierarchy (K3s)
+-- kubepods.slice
    +-- kubepods-burstable.slice
    |   +-- kubepods-burstable-pod<UID>.slice
    |       +-- cri-containerd-<ID>.scope   <-- pause
    |       +-- cri-containerd-<ID>.scope   <-- app container
    +-- kubepods-besteffort.slice
        +-- ...
```

| Параметр | Что контролирует |
|----------|-----------------|
| `cpu.max` | Лимит CPU (например, `100000 100000` = 1 core) |
| `memory.max` | Жёсткий лимит RAM (OOM kill при превышении) |
| `memory.high` | Мягкий лимит (throttling) |
| `io.max` | IOPS и bandwidth |
| `pids.max` | Максимум процессов (защита от fork-бомб) |

**cgroups v2 vs v1** — не просто "новая версия", а исправление архитектурных ошибок:
- **No Internal Process Rule:** процессы только в листовых узлах (устраняет race conditions)
- **Single Unified Hierarchy:** единое дерево вместо отдельного на каждый контроллер

### Overlay Filesystem — слои образа

```
+---------------------------------------+
|  Writable layer (upperdir)            |  <-- container writes here
+---------------------------------------+
|  Layer 3: COPY app.py                 |
+---------------------------------------+
|  Layer 2: RUN pip install             |  <-- read-only layers
+---------------------------------------+
|  Layer 1: FROM python:3.11            |
+---------------------------------------+
              | overlay mount
              v
+---------------------------------------+
|  /  (merged view for container)       |
+---------------------------------------+
```

**Copy-on-Write:** при модификации файла из read-only слоя, он копируется в writable слой. 100 контейнеров из одного образа используют одни и те же read-only слои.

**Практический нюанс:** каждый контейнер получает свой writable upperdir. При интенсивной записи (логи, temp-файлы) это может съедать место на хосте. Best practice — монтировать writable данные через volumes, rootfs держать read-only (`readOnlyRootFilesystem: true`).

### Модель безопасности

```
Container security (defense in depth):

  +-- seccomp          ~44 syscalls blocked (mount, reboot, kexec...)
  |   +-- Capabilities     drop ALL, add only needed
  |       +-- Namespaces   visibility isolation
  +-- AppArmor / SELinux profiles
  +-- read-only rootfs
  +-- no-new-privileges flag
```

**Но:** все контейнеры делят одно ядро. Эксплойт ядра = побег из контейнера. Это фундаментальное отличие от VM.

Для single-tenant кластера (как наш [[K3s]] с [[CVAT]]/[[ClearML]]) — теоретический риск. Для multi-tenant production — используют gVisor, Kata Containers, Firecracker.

### Историческая эволюция

```
1979  chroot (Unix V7)           — изоляция файловой системы
2000  FreeBSD Jails              — первая полноценная OS-level virtualization
2001  Linux-VServer              — контейнеры на Linux (патч ядра)
2004  Solaris Zones              — термин "container" входит в обиход
2005  OpenVZ                     — контейнеры на Linux (патч ядра)
2006  cgroups (Google → ядро)    — контроль ресурсов (Paul Menage, Rohit Seth)
2008  LXC                        — первый инструмент: namespaces + cgroups
2013  Docker                     — revolution в UX: Dockerfile, layers, Hub
2015  OCI                        — стандартизация формата образов и runtime
```

Docker **не изобрёл** контейнеры — он сделал их удобными (Dockerfile, registry, image layers). Docker изначально был обёрткой над LXC.

---

## Pod

### Зачем Pod, если есть контейнер?

Pod решает проблему **тесно связанных процессов**, которые должны разделять ресурсы. Аналогия из Unix: Pod — это **process group** (`pgrp`).

```
Unix Process Group               Kubernetes Pod
+-------------------+            +--------------------------+
| [P1]  [P2]        |            | [nginx]  [log-agent]     |
|                   |            |                          |
| Shared:           |            | Shared:                  |
|   terminal        |            |   network namespace      |
|   signals         |            |   IPC namespace          |
|   session         |            |   volumes, hostname      |
+-------------------+            +--------------------------+
```

| Паттерн | Описание | Пример |
|---------|----------|--------|
| **Sidecar** | Расширяет функционал основного контейнера | Envoy proxy, log-shipper |
| **Init Container** | Выполняется до запуска основных | DB migration, config download |
| **Ambassador** | Проксирование внешних соединений | Redis proxy |
| **Adapter** | Стандартизация вывода | Prometheus exporter |

### Pause container — скрытый фундамент

При создании Pod'а **первым** запускается `pause` container (`registry.k8s.io/pause`, ~700KiB).

```
Pod: cvat-server-xxxxx
+--------------------------------------------------+
|                                                  |
|  +------------------+                            |
|  | pause container  |  PID 1 in sandbox          |
|  | /pause           |                            |
|  |                  |  Creates & holds:           |
|  |                  |    - network namespace      |
|  |                  |    - IPC namespace          |
|  |                  |    - UTS namespace          |
|  |                  |                            |
|  |                  |  Pod IP is bound here       |
|  +--------+---------+                            |
|           | setns() -- containers join            |
|      +----+-----+    +----------+                |
|      |   app    |    | sidecar  |                |
|      |   :8080  |    |  :9090   |                |
|      +----------+    +----------+                |
|                                                  |
|  Both containers:                                |
|    - share localhost (same NET namespace)         |
|    - share one IP address                        |
|    - can use shared memory (IPC)                 |
|    - BUT have separate PID/MNT namespaces        |
+--------------------------------------------------+
```

**Зачем pause container:**

1. **Держит namespaces живыми.** Если app-контейнер крашится и рестартится — IP пода сохраняется, потому что pause жив
2. **Reaps zombies.** Как PID 1, pause вызывает `waitpid(-1, ...)` при SIGCHLD — собирает осиротевшие процессы. Без этого долгоживущие поды накапливали бы зомби до исчерпания `pids.max`
3. **Минимальный overhead.** Код: `for(;;) pause();` — бесконечный sleep. ~1MB RAM

### CRI: как kubelet создаёт Pod

```
kubelet --gRPC--> CRI shim (containerd)
                    |
                    +-- RunPodSandbox()     <-- pause + namespaces + CNI (IP)
                    |
                    +-- CreateContainer()   <-- app container joins sandbox
                    |
                    +-- StartContainer()    <-- start the container
```

**Pod Sandbox** — абстракция CRI. В containerd реализуется через pause container. В Kata Containers sandbox = microVM — тот же API, но аппаратная изоляция.

---

## Сравнительная таблица

| | **VM** | **Container** | **Pod** |
|---|---|---|---|
| **Что это** | Процесс гипервизора (QEMU/KVM) | Процесс Linux + namespaces + cgroups | Группа контейнеров + общие NS |
| **Ядро ОС** | Своё (гостевое) | Общее с хостом | Общее с хостом |
| **Изоляция** | Аппаратная (VT-x/AMD-V) | Программная (namespaces) | Программная (namespaces) |
| **Видимость в `ps aux`** | Только `qemu-*` | **ВСЕ процессы видны** | Все процессы + pause |
| **Overhead RAM** | 200MB+ | ~0 | ~1MB (pause) |
| **Время старта** | 10-60 сек | < 1 сек | 1-5 сек |
| **Сетевая модель** | Виртуальный NIC | veth pair + CNI | Общий NET NS |
| **Файловая система** | Виртуальный диск (qcow2) | Overlay FS (CoW) | Overlay + volumes |
| **Эксплойт ядра** | Не затрагивает хост | Побег из контейнера | Побег из контейнера |

---

## Ментальные модели

### Правильные

```
VM        = виртуальная аппаратная платформа с собственным ядром
Контейнер = изолированный процесс (с ограниченной видимостью и ресурсами)
Pod       = группа процессов с общими ресурсами (аналог process group)
```

### Опасные (неправильные)

- **"Контейнер = лёгкая VM"** — нет. Общее ядро, видимость процессов на хосте, другая модель безопасности
- **"Pod = просто несколько контейнеров вместе"** — нет. Важны общие namespaces через pause
- **"VM = один процесс"** — только для KVM/QEMU. Для Type-1 (ESXi) — ломается

---

## Практика — команды для исследования

Все команды выполняются на ноде [[K3s]] кластера (например, [[polydev-desktop]]).

### Контейнеры на хосте

```bash
# Список контейнеров K3s
sudo k3s crictl ps

# ВСЕ процессы контейнеров видны на хосте
ps auxf  # 'f' — дерево: containerd → shim → процесс

# Сколько Pod'ов = сколько pause
ps aux | grep '/pause' | grep -v grep | wc -l
```

### Namespaces

```bash
# Найти PID контейнера
CONTAINER_ID=$(sudo k3s crictl ps --name <имя> -q)
PID=$(sudo k3s crictl inspect $CONTAINER_ID | jq .info.pid)

# Все namespaces процесса
sudo ls -la /proc/$PID/ns/

# Все namespaces в системе
sudo lsns

# Войти в namespace контейнера
sudo nsenter -t $PID -n ip addr      # сетевой
sudo nsenter -t $PID -m ls /         # mount
sudo nsenter -t $PID -p -r ps aux    # PID
```

### Доказательство общего namespace в Pod'е

```bash
# 1. Найти Pod
POD_ID=$(sudo k3s crictl pods --namespace cvat --name cvat-server -q | head -1)

# 2. Контейнеры в Pod'е
sudo k3s crictl ps -a --pod $POD_ID

# 3. PID'ы pause и app контейнеров
PAUSE_PID=$(sudo k3s crictl inspect <pause_id> | jq .info.pid)
APP_PID=$(sudo k3s crictl inspect <app_id> | jq .info.pid)

# 4. Сравнить — NET одинаковый, PID разный
sudo readlink /proc/$PAUSE_PID/ns/net   # net:[4026532100]
sudo readlink /proc/$APP_PID/ns/net     # net:[4026532100] ← ОДИНАКОВЫЙ
sudo readlink /proc/$PAUSE_PID/ns/pid   # pid:[4026532098]
sudo readlink /proc/$APP_PID/ns/pid     # pid:[4026532099] ← РАЗНЫЙ
```

### Cgroups

```bash
# Cgroup контейнера
cat /proc/$PID/cgroup

# Лимиты (cgroups v2)
CGROUP_PATH=$(cat /proc/$PID/cgroup | cut -d: -f3)
cat /sys/fs/cgroup${CGROUP_PATH}/memory.max
cat /sys/fs/cgroup${CGROUP_PATH}/cpu.max

# Текущее потребление
cat /sys/fs/cgroup${CGROUP_PATH}/memory.current

# Дерево cgroups
sudo systemd-cgls
```

### Overlay filesystem

```bash
# Overlay mount'ы контейнеров
mount | grep overlay

# Mount info конкретного контейнера
cat /proc/$PID/mountinfo | head -5
```

---

## См. также

- [[Kubernetes]] — основные концепции
- [[Deployments]] — управление Pod'ами
- [[Services]] — сетевой доступ
- [[Kubernetes_Сеть_и_взаимодействие]] — сетевая модель
- [[K3s_Архитектура]] — архитектура нашего кластера

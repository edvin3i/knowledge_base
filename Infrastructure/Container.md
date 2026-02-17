---
tags:
  - containers
  - linux
  - theory
created: 2026-02-12
---

# Контейнер

> **В ядре Linux НЕТ сущности "контейнер".** Нет syscall `create_container()`. Контейнер — это конвенция userspace, комбинирующая три механизма ядра:

```
Container = Namespaces (изоляция видимости)
          + Cgroups (лимиты ресурсов)
          + Union FS (слоёная файловая система)
```

> Обзор и сравнение с VM/Pod: [[VM_Container_Pod]]

## Содержание

- [[#Контейнер vs VM — ключевое отличие]]
- [[#Linux Namespaces — изоляция видимости]]
- [[#Cgroups — ограничение ресурсов]]
- [[#Overlay Filesystem — слои образа]]
- [[#Модель безопасности]]
- [[#Историческая эволюция]]
- [[#Deep Dive — Container runtime]]
- [[#Deep Dive — Container security]]
- [[#Практика — команды для исследования]]

---

## Контейнер vs VM — ключевое отличие

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

В отличие от [[VirtualMachine|VM]], где гостевые процессы скрыты внутри одного процесса QEMU.

## Linux Namespaces — изоляция видимости

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

## Cgroups — ограничение ресурсов

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

## Overlay Filesystem — слои образа

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

## Модель безопасности

```
Container security (defense in depth):

  +-- seccomp          ~44 syscalls blocked (mount, reboot, kexec...)
  |   +-- Capabilities     drop ALL, add only needed
  |       +-- Namespaces   visibility isolation
  +-- AppArmor / SELinux profiles
  +-- read-only rootfs
  +-- no-new-privileges flag
```

**Но:** все контейнеры делят одно ядро. Эксплойт ядра = побег из контейнера. Это фундаментальное отличие от [[VirtualMachine|VM]].

Для single-tenant кластера (как наш [[K3s]] с [[CVAT]]/[[ClearML]]) — теоретический риск. Для multi-tenant production — используют gVisor, Kata Containers, Firecracker.

## Историческая эволюция

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

## Deep Dive — Container runtime

### Containerd-shim — невидимый посредник

Зачем нужен shim между containerd и runc:
- runc — короткоживущий: `runc create` + `runc start` → выход
- Без shim: restart containerd → pipes закрываются → контейнеры умирают
- Shim — долгоживущий daemon, отвязанный от containerd

```
Process tree on K3s node:

  systemd (PID 1)
    |
    +-- k3s-server (kubelet + containerd)
    |
    +-- containerd-shim-runc-v2 -namespace k8s.io -id <pod>
    |     |
    |     +-- /pause                    (pause container)
    |     +-- nginx: master process     (app container)
    |     |     +-- nginx: worker
    |     +-- python app.py             (sidecar)
    |
    +-- containerd-shim-runc-v2 -namespace k8s.io -id <pod2>
          |
          +-- /pause
          +-- redis-server
```

**Даемонизация shim'а:**
1. containerd вызывает `containerd-shim-runc-v2 start`
2. Шим fork'ается, дочерний процесс = daemon
3. Daemon: `setsid()` → новая сессия, отвязка от терминала
4. Daemon перенаправляет stdio в `/dev/null`
5. Родитель записывает PID + ttrpc-адрес на диск и завершается
6. Daemon reparent'ится к systemd

**Subreaper:** шим вызывает `prctl(PR_SET_CHILD_SUBREAPER, 1)` — осиротевшие потомки reparent'ятся к шиму, не к systemd. Шим получает exit-коды контейнеров через `waitpid()`.

**При restart containerd (K3s):**

```
1. containerd restarts (systemctl restart k3s)
2. shim processes NOT affected (children of systemd, not containerd)
3. Containers continue running (stdio pipes to shim are alive)
4. containerd finds shims via files in /run/containerd/
5. containerd reconnects via ttrpc sockets
6. State restored -- kubectl logs works again
```

### OCI Runtime Spec — что делает runc

**Двухфазное создание контейнера:**

```
runc create <container-id>
  |
  | 1. Read config.json from OCI bundle
  | 2. nsexec.c (GCC constructor, BEFORE Go runtime):
  |    a. PARENT: fork --> CHILD
  |    b. CHILD:  unshare(CLONE_NEWUSER)
  |               unshare(remaining namespaces)
  |    c. CHILD:  clone(CLONE_PARENT) --> INIT
  |    d. INIT:   setup network, hostname, mounts, seccomp
  |    e. INIT:   block on exec.fifo (named pipe)
  |
  | Container state: "created" (namespaces ready, user code NOT running)
  v
runc start <container-id>
  |
  | 1. Open exec.fifo --> unblocks INIT
  | 2. INIT calls execve() with args from config.json
  | 3. Container state: "running"
  v
```

**Зачем двухфазность:** между `create` и `start` CNI настраивает сеть, volumes готовятся. Контейнер гарантированно запускается с уже готовой инфраструктурой.

**Зачем nsexec.c вызывается как GCC constructor (до Go runtime):** Go использует потоки, а `setns()` работает per-thread. На этапе constructor потоков ещё нет — можно безопасно переключить namespace.

**Трёхфазный fork в nsexec.c:**

```
PARENT --> clone() --> CHILD
                        |
                        unshare(CLONE_NEWPID | CLONE_NEWNET | ...)
                        |
                        clone(CLONE_PARENT) --> INIT
                                                  |
                                                  INIT is PID 1 in new PID NS
                                                  (because unshare creates NS,
                                                   but caller stays in OLD NS;
                                                   only children enter NEW NS)
```

---

## Deep Dive — Container security

### Linux Capabilities — декомпозиция root

Исторически root (UID 0) = все привилегии. Capabilities (Linux 2.2+) разбивают root на ~41 дискретных привилегий.

**Пять наборов capabilities процесса:**

| Набор | Назначение |
|-------|-----------|
| **Permitted (P)** | Максимум, что процесс МОЖЕТ активировать |
| **Effective (E)** | Что реально используется для проверок ядра |
| **Inheritable (I)** | Что сохраняется через `execve()` |
| **Bounding (B)** | Верхний предел: P' = P_file AND B |
| **Ambient (A)** | Наследуемые без file capabilities (4.3+) |

**Capabilities критичные для контейнеров:**

| Capability | Что позволяет | Docker default |
|------------|--------------|----------------|
| `CAP_SYS_ADMIN` | mount, namespace creation, BPF (~"полу-root") | DROP |
| `CAP_NET_ADMIN` | iptables, routing, interface config | DROP |
| `CAP_NET_RAW` | RAW/PACKET сокеты (tcpdump, ping) | KEEP |
| `CAP_SYS_PTRACE` | `ptrace()`, `/proc/PID/mem` чтение | DROP |
| `CAP_SYS_MODULE` | Загрузка модулей ядра | DROP |
| `CAP_NET_BIND` | Привязка к портам < 1024 | KEEP |

**Bounding set необратим:** `prctl(PR_CAPBSET_DROP, cap)` удаляет capability, восстановить невозможно (даже для root). Container runtime устанавливает bounding set ДО запуска.

### Seccomp-BPF — фильтрация syscalls

Seccomp-BPF (Linux 3.5+) применяет BPF-программы для фильтрации системных вызовов:

```
Process calls syscall
  |
  v
seccomp BPF program (in kernel)
  |  Input: syscall number, args, arch
  |
  v
Action:
  SCMP_ACT_ALLOW  --> Allow syscall
  SCMP_ACT_ERRNO  --> Return error (EPERM)
  SCMP_ACT_TRAP   --> Send SIGSYS
  SCMP_ACT_KILL   --> Kill process
  SCMP_ACT_LOG    --> Allow + log
```

**Ключевые заблокированные syscalls (Docker default profile):**

| Syscall | Почему заблокирован |
|---------|-------------------|
| `mount` / `umount` | Монтирование FS = побег из overlay |
| `reboot` / `kexec_load` | Перезагрузка хоста из контейнера |
| `clone + CLONE_NEWUSER` | Создание user NS = потенциальный escape |
| `ptrace` | Отладка других процессов = чтение памяти |
| `bpf` | Загрузка BPF-программ в ядро |
| `io_uring_*` | Множество CVE в подсистеме io_uring |

**Defense in depth:** даже если одна линия обороны обойдена — другие остаются:

```
mount() syscall:
  Check 1: Capabilities --> CAP_SYS_ADMIN? No --> EPERM
  Check 2: Seccomp-BPF --> mount() allowed? No --> EPERM
  Check 3: AppArmor/SELinux --> profile allows? ...
```

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

### Containerd-shim и OCI bundle

```bash
# Дерево: shim -> pause -> app
ps auxf | grep -A5 containerd-shim

# Все shim'ы (= количество sandbox'ов/pod'ов)
ps aux | grep 'containerd-shim-runc-v2' | grep -v grep | wc -l

# Проверить subreaper
SHIM_PID=$(pgrep -f 'containerd-shim' | head -1)
sudo grep -i subreaper /proc/$SHIM_PID/status
# Subreaper:  1

# OCI bundle контейнера
CONTAINER_ID=$(sudo k3s crictl ps --name cvat-server -q | head -1)
BUNDLE="/run/containerd/io.containerd.runtime.v2.task/k8s.io/$CONTAINER_ID"
sudo cat $BUNDLE/config.json | jq '{
  namespaces: .linux.namespaces,
  args: .process.args,
  capabilities: .process.capabilities.bounding
}'
```

---

## См. также

- [[VM_Container_Pod]] — обзор и сравнение VM / Container / Pod
- [[VirtualMachine]] — виртуальные машины
- [[Pod]] — Kubernetes Pod
- [[Docker]] — контейнерный инструмент
- [[Kubernetes]] — основные концепции

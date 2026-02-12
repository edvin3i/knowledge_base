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
- [[#Ментальные модели]]
- [[#Deep Dive — VM internals]]
- [[#Deep Dive — Pause container]]
- [[#Deep Dive — Container runtime]]
- [[#Deep Dive — Pod lifecycle]]
- [[#Deep Dive — Container security]]
- [[#Deep Dive — Composition patterns]]
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

## Deep Dive — VM internals

### 17 проблемных инструкций x86

Робин и Ирвин (USENIX Security, 2000) формально показали, что 17 инструкций x86 являются sensitive, но НЕ privileged — они не вызывают trap в Ring 3:

| Группа | Инструкции | Проблема |
|--------|-----------|----------|
| **Флаг прерываний** | `PUSHF`, `POPF`, `IRET` | `POPF` молча игнорирует изменение IF в Ring 3. Гость думает что отключил прерывания |
| **Привилегированные регистры** | `SGDT`, `SIDT`, `SLDT`, `SMSW`, `STR` | Чтение реальных таблиц хоста (GDT, IDT). Утечка адресов |
| **Сегментные регистры** | `MOV seg`, `PUSH seg`, `POP seg` | Чтение/запись сегментных регистров без trap |
| **Дескрипторы** | `LAR`, `LSL`, `VERR`, `VERW` | Проверка дескрипторных таблиц — утечка конфигурации |
| **Управление потоком** | `CALL far`, `JMP far`, `RET far`, `INT n` | Дальние переходы через сегменты |

Пример: `SGDT` в Ring 3 вернёт реальный адрес GDT хоста. Гость увидит физическую конфигурацию — нарушение свойства Equivalence.

### Решения до VT-x

**Binary Translation (VMware, 1999):**

```
Original guest code:              After translation:

  pushf                             call vmm_emulate_pushf
  popf                              call vmm_emulate_popf
  sgdt [eax]                        call vmm_emulate_sgdt
  mov eax, [ebx]                    mov eax, [ebx]    <-- no change
  add eax, 1                        add eax, 1        <-- no change
```

VMware сканирует код ядра гостя и заменяет проблемные инструкции вызовами эмулятора. Непривилегированный код (Ring 3 гостя) исполняется без трансляции. Overhead: ~2-5% CPU для типичных нагрузок.

**Паравиртуализация (Xen, 2003):** гостевое ядро модифицируется при компиляции — вместо привилегированных инструкций используются hypercall (аналог syscall для VMM). Лучшая производительность, но требует модификации гостевого ядра.

### EPT/NPT — nested page walk (детально)

Три адресных пространства виртуализированной среды:

```
Guest Virtual Address (GVA)
        |
        | Guest page tables (CR3)
        v
Guest Physical Address (GPA)
        |
        | EPT/NPT (hardware)
        v
Host Physical Address (HPA)
```

**Без EPT (Shadow Page Tables):** VMM поддерживает "теневые" таблицы GVA -> HPA. При каждом обновлении гостевых таблиц — VM Exit + пересчёт. Overhead: до 75% для memory-intensive нагрузок.

**С EPT — worst case TLB miss:**

```
4-level guest PT x 4-level EPT = nested walk:

  1. PML4E (guest)  -> EPT walk (4 reads) -> HPA
  2. PDPE  (guest)  -> EPT walk (4 reads) -> HPA
  3. PDE   (guest)  -> EPT walk (4 reads) -> HPA
  4. PTE   (guest)  -> EPT walk (4 reads) -> HPA
  5. Data page      -> EPT walk (4 reads) -> HPA

  Total: 4 * 4 + 4 = 20 memory accesses per TLB miss
```

На практике paging-structure caches и L1/L2 кэши удовлетворяют большинство обращений. Реальный overhead: ~5-10%.

**VPID (Virtual Processor ID) — tagged TLB:**

```
Without VPID:                      With VPID:

  VM Exit/Entry:                     VM Exit/Entry:
  FLUSH entire TLB!                  TLB preserved!
  (all entries lost)                 (entries tagged by VPID)
  Hundreds of TLB misses            Immediate continuation
```

VPID добавляет 16-битный тег к каждой TLB-записи. При VM switch процессор НЕ сбрасывает TLB — записи разных VM различаются по VPID.

### VMCS (Virtual Machine Control Structure)

Аппаратная структура Intel (4 KiB) для каждого vCPU:

```
+---------------------------------------------------+
|                   VMCS (4 KiB)                     |
+---------------------------------------------------+
| Guest-state area:                                  |
|   CR0, CR3, CR4, DR7, RSP, RIP, RFLAGS            |
|   Segment registers, GDTR, LDTR, IDTR, TR, MSRs   |
+---------------------------------------------------+
| Host-state area:                                   |
|   CR0, CR3, CR4, RSP, RIP, segment selectors       |
+---------------------------------------------------+
| VM-execution controls:                             |
|   Pin-based, Processor-based, Exception bitmap     |
|   EPT pointer, VPID                               |
+---------------------------------------------------+
| VM-exit information (read-only):                   |
|   Exit reason, Exit qualification                  |
|   Guest-linear/physical address                    |
+---------------------------------------------------+
```

**Цикл жизни VM:**

```
VMXON        --> Enable VMX mode
VMCLEAR      --> Init VMCS
VMPTRLD      --> Load VMCS as active
VMLAUNCH     --> First guest entry (load guest-state)
               |
               +--- Guest code execution ---+
               |                            |
               |   (privileged operation)    |
               v                            v
VM EXIT      <-- Auto: save guest-state, load host-state,
               |       record exit reason
               |
               +--- KVM handles exit reason ---+
               |
VMRESUME     --> Re-enter guest
```

**Основные причины VM Exit:**

| Exit reason | Типичная обработка |
|-------------|-------------------|
| I/O instruction (`IN`/`OUT`) | QEMU эмулирует устройство |
| `CPUID` | KVM подставляет виртуальные данные |
| EPT violation | KVM обновляет EPT или инжектирует #PF |
| External interrupt | KVM обрабатывает прерывание хоста |
| `HLT` | KVM переключает vCPU thread на sleep |
| CR access | KVM обновляет shadow/EPT |

---

## Deep Dive — Pause container

### Исходный код pause.c

Файл: `kubernetes/build/pause/linux/pause.c` (~30 строк C):

```c
static void sigdown(int signo) {
  psignal(signo, "Shutting down, got signal");
  exit(0);
}

static void sigreap(int signo) {
  while (waitpid(-1, NULL, WNOHANG) > 0)
    ;
}

int main(int argc, char **argv) {
  if (getpid() != 1)
    fprintf(stderr, "Warning: pause should be the first process\n");

  if (sigaction(SIGINT,  &(struct sigaction){.sa_handler = sigdown}, NULL) < 0)
    return 1;
  if (sigaction(SIGTERM, &(struct sigaction){.sa_handler = sigdown}, NULL) < 0)
    return 2;
  if (sigaction(SIGCHLD, &(struct sigaction){.sa_handler = sigreap,
    .sa_flags = SA_NOCLDSTOP}, NULL) < 0)
    return 3;

  for (;;)
    pause();

  fprintf(stderr, "Error: infinite loop terminated\n");
  return 42;
}
```

### Разбор по строкам

**`sigdown()`** — обработчик SIGINT/SIGTERM. Graceful shutdown: печатает описание сигнала и вызывает `exit(0)`.

**`sigreap()`** — zombie reaper:
- `waitpid(-1, NULL, WNOHANG)` — собирает **любой** завершённый дочерний процесс без блокировки
- Цикл `while > 0` — собирает **все** зомби за один вызов (ядро может coalesce несколько SIGCHLD в один)
- `NULL` вместо `&status` — exit code не нужен, просто убираем зомби

**`SA_NOCLDSTOP`** — не получать SIGCHLD при остановке ребёнка (SIGSTOP/SIGTSTP), только при завершении.

**`getpid() != 1`** — предупреждение если pause не PID 1 (но не ошибка).

**`for (;;) pause()`** — бесконечный цикл с syscall `pause()`.

### Почему `pause()` а не `sleep()`

| | `pause()` | `sleep()` / `nanosleep()` |
|---|---|---|
| **Состояние ядра** | `TASK_INTERRUPTIBLE` | `TASK_INTERRUPTIBLE` |
| **Таймер** | Нет | Создаёт `hrtimer` |
| **Возврат** | Только по сигналу (EINTR) | По таймеру или сигналу |
| **Семантика** | "Жди сигнала" | "Жди N секунд" |
| **Overhead** | Нет (нет таймера) | Создание/удаление таймера каждый цикл |

`pause()` семантически точен: pause container ждёт сигналы, а не время. Экономит ресурсы ядра (нет hrtimer).

### PID 1 — теория init-процесса (POSIX)

PID 1 в POSIX имеет уникальные свойства:

1. **Reparenting orphans:** когда родитель умирает, дочерние процессы переназначаются к PID 1
2. **Обязанность reaping:** PID 1 ОБЯЗАН вызывать `wait()` для усыновлённых, иначе зомби навечно
3. **Иммунитет к сигналам:** ядро не доставляет PID 1 сигналы без явного обработчика. `kill -9 1` на хосте НЕ убьёт init (но в PID namespace контейнера — убьёт, начиная с Linux 3.4)

**Zombie формально:** процесс в состоянии `EXIT_ZOMBIE` — завершил исполнение, но запись в `task_struct` (~6 KiB) сохраняется до вызова `wait()` родителем. Зомби не занимают RAM/CPU, но тратят PID (ограничен `pid_max`, default 32768). При `pids.max` в cgroup — накопление зомби может исчерпать лимит.

**`prctl(PR_SET_CHILD_SUBREAPER)` vs PID 1:**

```
PID 1 (init/systemd)
  |
  +-- subreaper (containerd-shim, PR_SET_CHILD_SUBREAPER=1)
  |     |
  |     +-- process A
  |     |     |
  |     |     +-- orphan --> reparent to subreaper (NOT PID 1)
```

Subreaper "перехватывает" осиротевших потомков. Containerd-shim использует это для получения exit-кодов контейнеров.

### Сравнение init-процессов для контейнеров

| Init | Размер | Reaping | Signal forwarding | Когда использовать |
|------|--------|---------|-------------------|-------------------|
| **pause** | ~700KB | Да | Нет | Kubernetes (kubelet управляет контейнерами через CRI) |
| **tini** | ~20KB | Да | Да (SIGTERM etc) | Docker `--init` (standalone контейнеры) |
| **dumb-init** | ~50KB | Да | Да + rewriting | Docker (Yelp, аналог tini) |
| **systemd** | ~10MB | Да | Да + services | "Fat containers" (antipattern) |

### Что произойдёт если pause умрёт

```
pause process dies (crash / OOM / kill)
  |
  v
containerd-shim detects sandbox exit
  |
  v
containerd notifies kubelet via CRI event stream
  |
  v
kubelet: sandbox failed --> stop ALL containers in Pod
  |
  v
kubelet: RemovePodSandbox() --> CNI DEL
  |
  v
CNI (Flannel): delete veth pair, release IP from IPAM
  |
  v
Pod --> Failed, kubelet requests re-schedule
(depending on restartPolicy)
```

Namespace'ы в Linux существуют пока есть процесс или bind mount. Containerd делает bind mount namespace'ов sandbox'а. Но kubelet всё равно убьёт Pod — смерть sandbox = смерть Pod'а.

### Альтернативы pause

| Подход | Sandbox | Изоляция | Overhead |
|--------|---------|----------|----------|
| **runc + pause** (default) | Процесс `/pause` | Программная (namespaces) | ~1 MiB |
| **Kata Containers** | Lightweight VM (QEMU/Cloud Hypervisor) + kata-agent | Аппаратная (VT-x) | ~30-50 MiB, ~100ms boot |
| **gVisor (runsc)** | Sentry process (userspace kernel на Go, ~200 syscalls) | Программная (syscall filter) | ~15 MiB |
| **CRI-O + crun** | conmon process (аналог shim) | Программная (namespaces) | ~0.5 MiB |

### Namespace theory — формальная модель

**Определение:** namespace = partition ресурсного пространства ядра. Отображение `N: R_global -> R_visible`.

**Иерархические vs плоские:**

```
PID namespace -- HIERARCHICAL       NET namespace -- FLAT

  PID NS 1 (host)                    NET NS "host"
    |                                 NET NS "pod-A"
    +-- PID NS 2 (pod)               NET NS "pod-B"
    |     |                           (all independent,
    |     +-- PID NS 3                 no parent-child)
    +-- PID NS 4 (pod)
```

- **PID** иерархический: родитель видит всех потомков (с маппингом PID), потомки не видят родителя. Нужно для `ptrace()`, метрик, отладки.
- **NET** плоский: взаимодействие через veth pairs и routing, нет семантики "родительского" стека.

**Reference counting:** namespace живёт пока есть хотя бы один процесс ИЛИ bind mount на `/proc/PID/ns/*`. Pause держит namespace через своё существование.

**Ограничение `setns()` для PID namespace:** `setns(fd, CLONE_NEWPID)` НЕ меняет PID NS вызывающего процесса — только для будущих дочерних через `fork()`. Причина: PID назначается при создании и не может быть изменён.

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

## Deep Dive — Pod lifecycle

### Полная цепочка: от kubectl до первого пакета

```
kubectl run nginx --image=nginx
  |
  | HTTP POST /api/v1/namespaces/default/pods
  | (TLS, bearer token, RBAC, admission webhooks)
  v
API Server --> etcd (Raft consensus, persisted)
  |             Pod object saved (nodeName empty)
  v
Scheduler (watch loop)
  |  Sees unscheduled Pod (nodeName == "")
  |  Filtering: NodeAffinity, Taints, Resources
  |  Scoring: LeastAllocated, ImageLocality
  |  Result: nodeName = "polydev-desktop"
  |  PATCH pods/nginx {spec.nodeName: "polydev-desktop"}
  v
Kubelet on polydev-desktop (watch loop)
  |  Sees new Pod assigned to this node
  |  1. Admission: resources, PodSecurityStandards
  |  2. Volumes: wait for Longhorn attach + mount
  v
CRI: RunPodSandbox()
  |
  v
containerd:
  |  1. Pull registry.k8s.io/pause:3.10 (if not cached)
  |  2. Create OCI bundle (config.json + rootfs)
  |  3. Launch containerd-shim-runc-v2
  v
containerd-shim:
  |  1. Daemonize (fork + setsid + reparent to systemd)
  |  2. Open ttrpc socket
  |  3. Call runc create <sandbox-id>
  v
runc:
  |  nsexec.c:
  |    PARENT -> CHILD -> unshare(namespaces) -> INIT
  |    INIT blocks on exec.fifo
  |  runc start -> INIT execve("/pause")
  v
CNI (Flannel):
  |  1. Create veth pair: vethXXXX <--> eth0
  |  2. Move one end into sandbox network namespace
  |  3. Attach other end to bridge cni0 on host
  |  4. IPAM: allocate IP from node subnet (10.42.X.Y/24)
  |  5. Setup routes inside namespace
  v
CRI: CreateContainer() + StartContainer()
  |  1. containerd creates OCI bundle for nginx
  |  2. runc: does NOT create new NET/IPC/UTS namespaces
  |     Instead: setns() to sandbox namespaces (from pause)
  |     Creates ONLY own PID and MNT namespaces
  |  3. nginx starts: sees eth0 with Pod IP, shared localhost
  v
Pod Running -- first packet can be sent!
```

### Ключевые системные вызовы

| Этап | Syscall | Что делает |
|------|---------|------------|
| Создание sandbox | `unshare(CLONE_NEW*)` | Создание namespace'ов |
| Fork INIT | `clone(CLONE_PARENT)` | PID 1 в новом PID NS |
| Запуск pause | `execve("/pause")` | Замена процесса |
| CNI: veth | `socket(AF_NETLINK)` + netlink | Создание veth pair |
| CNI: move veth | `setns(fd, CLONE_NEWNET)` | Переместить veth в NS |
| App joins NS | `setns(fd, CLONE_NEWNET)` | Контейнер входит в NET NS sandbox'а |
| App запуск | `execve("/usr/sbin/nginx")` | Запуск приложения |
| Pause ждёт | `pause()` | `TASK_INTERRUPTIBLE` |

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

## Deep Dive — Composition patterns

### Pod как единица co-scheduling

**Формально:** Pod = {C_1, C_2, ..., C_n} где:
1. Все C_i scheduled на одну ноду (co-location)
2. Все C_i разделяют network identity (один IP, один hostname)
3. Все C_i запускаются/останавливаются как единица (co-lifecycle)

**Shared fate:** если pause умирает — весь Pod умирает. Аналогия: когда session leader умирает, все процессы в session group получают SIGHUP.

### Паттерны Burns & Oppenheimer (HotCloud 2016, USENIX)

Burns и Oppenheimer формализовали три single-node паттерна (по аналогии с GoF Design Patterns):

**1. Sidecar — расширение без модификации:**

```
+---------------------------+
| Pod                       |
|  +-------+  +----------+ |
|  |  Main  |  | Sidecar  | |
|  | (app)  |  | (extend) | |
|  +---+----+  +----+-----+ |
|      |            |        |
|      +-- shared --+        |
|         volume            |
+---------------------------+
```

Примеры: log-shipping (app пишет в /var/log, sidecar отправляет в ELK), TLS termination (Envoy на :443, проксирует в app на :8080).

**2. Ambassador — проксирование внешних сервисов:**

```
+---------------------------+
| Pod                       |
|  +-------+  +----------+ |
|  |  Main  |  |Ambassador| |
|  | (app)  |  | (proxy)  | |
|  +---+----+  +----+-----+ |
|      |            |        |
|      +--localhost--+       |
+-----------|---------------+
            v
      External Service
```

Примеры: Redis Sentinel proxy (app -> localhost:6379 -> ambassador -> выбор мастера), DB sharding proxy.

**3. Adapter — стандартизация вывода:**

```
+---------------------------------+
| Pod                             |
|  +-------+  +--------------+   |
|  |  Main  |  |   Adapter    |   |
|  | (app)  |  | (standardize)|   |
|  +---+----+  +------+-------+   |
|      |              |            |
|      +-- shared ----+            |
|         volume                  |
+---------------------------------+
```

Примеры: Prometheus exporter (читает проприетарные метрики, выдаёт /metrics в формате Prometheus), log format adapter (проприетарный формат -> structured JSON).

**Ключевое наблюдение:** эти паттерны возможны ТОЛЬКО благодаря Pod-абстракции (shared namespaces). Без общего localhost и volumes — sidecar/ambassador/adapter потребовали бы межнодовой сетевой коммуникации.

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

### Сеть Pod'а (veth pairs)

```bash
# Все veth на хосте
ip link show type veth

# Bridge cni0 и подключённые veth'ы
bridge link show

# IP/routes внутри pod'а (через nsenter)
PAUSE_PID=<pid>
sudo nsenter -t $PAUSE_PID -n ip addr show eth0
sudo nsenter -t $PAUSE_PID -n ip route

# ARP таблица внутри pod namespace
sudo nsenter -t $PAUSE_PID -n ip neigh
```

### Трассировка создания namespace (advanced)

```bash
# Увидеть unshare/clone при создании контейнера
# (в одном терминале strace, в другом — kubectl run test --image=busybox)
sudo strace -f -e trace=clone,clone3,unshare,setns,execve \
  -p $(pgrep -f 'containerd-shim-runc-v2.*k8s.io') 2>&1 | head -50

# Сравнение всех namespace'ов pause vs app (diff)
diff <(sudo readlink /proc/$PAUSE_PID/ns/*) <(sudo readlink /proc/$APP_PID/ns/*)
```

---

## См. также

- [[Kubernetes]] — основные концепции
- [[Deployments]] — управление Pod'ами
- [[Services]] — сетевой доступ
- [[Kubernetes_Сеть_и_взаимодействие]] — сетевая модель
- [[K3s_Архитектура]] — архитектура нашего кластера

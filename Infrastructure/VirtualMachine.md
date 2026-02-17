---
tags:
  - virtualization
  - linux
  - theory
created: 2026-02-12
---

# Виртуальная машина (VM)

VM — **процесс гипервизора**, внутри которого работает полноценная гостевая ОС со своим ядром. Гостевые процессы **не видны** на хосте.

> Обзор и сравнение с контейнерами/подами: [[VM_Container_Pod]]

## Содержание

- [[#Что это на уровне хоста]]
- [[#Архитектура виртуализации]]
- [[#Аппаратная виртуализация VT-x / AMD-V]]
- [[#Критерии Попека-Голдберга (1974)]]
- [[#Type-1 vs Type-2 гипервизоры]]
- [[#Deep Dive — VM internals]]

---

## Что это на уровне хоста

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

## Архитектура виртуализации

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

## Аппаратная виртуализация: VT-x / AMD-V

Каждый vCPU thread выполняет инструкцию `VMENTER`, передавая управление гостевому коду **напрямую на процессоре**. При привилегированных операциях происходит `VMEXIT` обратно в KVM. Это аппаратная виртуализация — не эмуляция.

**Виртуализация памяти (EPT/NPT):** процессор аппаратно выполняет двухуровневую трансляцию Guest VA → Guest PA → Host PA, устраняя необходимость в shadow page tables. Это даёт до 48% прироста для memory-intensive нагрузок.

## Критерии Попека-Голдберга (1974)

Формальное определение Virtual Machine Monitor (VMM) — три свойства:

1. **Equivalence:** программа под VMM ведёт себя идентично исполнению на реальном железе
2. **Efficiency:** доминирующее подмножество инструкций исполняется напрямую на процессоре
3. **Resource Control:** VMM полностью контролирует ресурсы, ни одна программа не обойдёт его

> **Теорема:** VMM может быть построен тогда и только тогда, когда множество *sensitive instructions* является подмножеством *privileged instructions*.

**Проблема x86:** архитектура x86 не удовлетворяла этим критериям — некоторые sensitive-инструкции (`POPF`, `SGDT`) не вызывали trap. Решения до VT-x: binary translation (VMware), paravirtualization (Xen). После VT-x/AMD-V (2005-2006) — аппаратный trap-and-emulate.

## Type-1 vs Type-2 гипервизоры

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

**VPID (Virtual Processor Id) — tagged TLB:**

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

## См. также

- [[VM_Container_Pod]] — обзор и сравнение VM / Container / Pod
- [[Container]] — контейнеры Linux
- [[Pod]] — Kubernetes Pod
- [[Kubernetes]] — основные концепции

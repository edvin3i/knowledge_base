---
tags:
  - kubernetes
  - linux
  - containers
  - theory
created: 2026-02-12
---

# Pod

Pod — минимальная единица развёртывания в Kubernetes. Группа контейнеров с **общими namespaces** (сеть, IPC, hostname).

> Обзор и сравнение с VM/контейнерами: [[VM_Container_Pod]]

## Содержание

- [[#Зачем Pod, если есть контейнер?]]
- [[#Pause container — скрытый фундамент]]
- [[#CRI: как kubelet создаёт Pod]]
- [[#Deep Dive — Pause container]]
- [[#Deep Dive — Pod lifecycle]]
- [[#Deep Dive — Composition patterns]]
- [[#Практика — команды для исследования]]

---

## Зачем Pod, если есть контейнер?

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

## Pause container — скрытый фундамент

**Pause — это программа на C (~30 строк)**, скомпилированная в бинарник `/pause` и упакованная в минимальный контейнерный образ `registry.k8s.io/pause:3.10` (~700 KiB). Весь смысл программы — три строки: `for(;;) pause();` — бесконечный сон, пробуждение только по сигналу.

Pause нужен не для того чтобы **делать** что-то, а для того чтобы **существовать** — его жизнь = жизнь namespace'ов Pod'а.

**Проблема:** Pod = несколько контейнеров с общей сетью. Кто-то должен создать и удерживать общий network namespace. Если доверить это рабочему контейнеру (nginx, redis) — при его крэше namespace умрёт, IP пода потеряется, все остальные контейнеры сломаются.

**Решение:** запустить отдельный "пустой" контейнер первым:

```
Timeline создания Pod'а:

  1. kubelet -> containerd: "create sandbox"
     --> containerd runs pause:3.10
     --> namespaces created (NET, IPC, UTS)
     --> CNI assigns IP (e.g. 10.42.0.15)
     --> /pause starts and sleeps

  2. kubelet -> containerd: "create app container IN SAME sandbox"
     --> runc calls setns() to pause's namespaces
     --> nginx starts, sees eth0 with 10.42.0.15

  3. nginx crashes:
     --> pause is alive --> namespace alive --> IP preserved
     --> kubelet restarts only nginx
     --> nginx re-joins same namespace
     --> same IP, nothing broke
```

**Аналогия:** коммунальная квартира. Pause — арендатор, подписавший договор (создал namespace) и просто спящий в углу. App-контейнеры — соседи, подселяющиеся к нему и пользующиеся общей кухней (localhost) и общим адресом (IP). Если сосед съехал и вернулся — квартира та же, адрес тот же, потому что договор на имя pause.

При создании Pod'а **первым** запускается pause container:

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

## CRI: как kubelet создаёт Pod

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

- [[VM_Container_Pod]] — обзор и сравнение VM / Container / Pod
- [[VirtualMachine]] — виртуальные машины
- [[Container]] — контейнеры Linux
- [[Kubernetes]] — основные концепции
- [[Deployments]] — управление Pod'ами
- [[Services]] — сетевой доступ
- [[Kubernetes - Сеть и взаимодействие]] — сетевая модель

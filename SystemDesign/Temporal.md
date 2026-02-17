---
tags:
  - system-design
  - orchestration
  - temporal
created: 2026-02-17
---

# Глубокое погружение в архитектуру Temporal

## Что это
Temporal -- платформа устойчивого выполнения (durable execution) с открытым исходным кодом, упрощающая создание надёжных распределённых приложений. Форк проекта Uber Cadence (2019). Использует Event Sourcing для автоматического сохранения и восстановления состояния workflow.

## What is Temporal? / Что такое Temporal?

**Temporal** is an open-source durable execution platform that simplifies building reliable distributed applications. It's a fork of Uber's Cadence project (2019).

**Temporal** -- это платформа устойчивого выполнения с открытым исходным кодом, упрощающая создание надёжных распределённых приложений. Это форк проекта Uber Cadence (2019).

### Core Value Proposition / Основное ценностное предложение

**Problem:** Distributed systems fail in complex ways -- network partitions, process crashes, timeouts.

**Solution:** Write workflow logic as regular code, Temporal handles:
- State persistence (automatic)
- Failure recovery (automatic replay)
- Retries with backoff
- Long-running timers (days, weeks, months)

```
┌─────────────────────────────────────────────────────────────────────┐
│  TRADITIONAL APPROACH                                               │
│                                                                      │
│  Developer must handle:                                             │
│  • Save state to database after each step                          │
│  • Implement retry logic with exponential backoff                  │
│  • Handle idempotency manually                                      │
│  • Manage distributed locks                                         │
│  • Track workflow progress in database                              │
│  • Handle partial failures and compensations                        │
│                                                                      │
│  Result: 60%+ of code is error handling, not business logic        │
├─────────────────────────────────────────────────────────────────────┤
│  TEMPORAL APPROACH                                                  │
│                                                                      │
│  Developer writes:                                                  │
│  • Business logic as regular functions                              │
│  • Activity implementations (external calls)                        │
│                                                                      │
│  Temporal handles everything else automatically                     │
│                                                                      │
│  Result: Clean code focused on business logic                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Architecture Components / Компоненты архитектуры

### High-Level Architecture / Высокоуровневая архитектура

```
┌─────────────────────────────────────────────────────────────────────┐
│                         TEMPORAL CLUSTER                            │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │  Frontend   │  │   History   │  │  Matching   │                 │
│  │  Service    │  │   Service   │  │   Service   │                 │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │
│         │                │                │                         │
│         └────────────────┼────────────────┘                         │
│                          │                                          │
│                    ┌─────┴─────┐                                    │
│                    │ Persistence│                                   │
│                    │  (MySQL/   │                                   │
│                    │ PostgreSQL/│                                   │
│                    │ Cassandra) │                                   │
│                    └───────────┘                                    │
└─────────────────────────────────────────────────────────────────────┘
         │                                    │
         ▼                                    ▼
┌─────────────────┐                  ┌─────────────────┐
│  Worker Process │                  │  Worker Process │
│  ┌───────────┐  │                  │  ┌───────────┐  │
│  │ Workflow  │  │                  │  │ Activity  │  │
│  │ Worker    │  │                  │  │ Worker    │  │
│  └───────────┘  │                  └───────────────┘
└─────────────────┘
```

### Service Breakdown / Разбор сервисов

#### 1. Frontend Service / Фронтенд-сервис

**Role:** API gateway for all client requests.

**Роль:** API-шлюз для всех клиентских запросов.

**Responsibilities / Обязанности:**
- Rate limiting / Ограничение частоты запросов
- Authorization / Авторизация
- Request routing / Маршрутизация запросов
- gRPC API endpoint / gRPC API эндпоинт

```
┌─────────────────────────────────────────────────────────────────────┐
│  FRONTEND SERVICE                                                   │
│                                                                      │
│  Client Request                                                     │
│       │                                                             │
│       ▼                                                             │
│  ┌─────────┐                                                        │
│  │  Rate   │ ─ Reject if limit exceeded                            │
│  │ Limiter │                                                        │
│  └────┬────┘                                                        │
│       │                                                             │
│       ▼                                                             │
│  ┌─────────┐                                                        │
│  │  AuthZ  │ ─ Check namespace permissions                         │
│  └────┬────┘                                                        │
│       │                                                             │
│       ▼                                                             │
│  ┌─────────┐     Route to History Service                          │
│  │ Router  │───────────────────────────────────────►               │
│  └─────────┘                                                        │
└─────────────────────────────────────────────────────────────────────┘
```

#### 2. History Service / Сервис истории

**Role:** Core workflow execution engine. This is the "brain" of Temporal.

**Роль:** Ядро движка выполнения workflow. Это "мозг" Temporal.

**Key Concept: History Shards / Ключевая концепция: Шарды истории**

Each workflow execution is assigned to a **History Shard**. This is the fundamental scalability mechanism.

Каждое выполнение workflow привязывается к **Шарду истории**. Это фундаментальный механизм масштабируемости.

```
┌─────────────────────────────────────────────────────────────────────┐
│  HISTORY SERVICE with SHARDS                                        │
│                                                                      │
│  Workflow ID: "order-12345"                                         │
│       │                                                             │
│       ▼                                                             │
│  hash("order-12345") % NUM_SHARDS = Shard 42                       │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                    HISTORY SERVICE CLUSTER                     │ │
│  │                                                                 │ │
│  │  Instance A         Instance B         Instance C              │ │
│  │  ┌─────────┐       ┌─────────┐       ┌─────────┐             │ │
│  │  │Shard 0-3│       │Shard 4-7│       │Shard 8-11│            │ │
│  │  │   ...   │       │   ...   │       │   ...    │            │ │
│  │  │Shard 40 │       │Shard 41 │       │Shard 42  │◄── HERE    │ │
│  │  │Shard 43 │       │Shard 44 │       │Shard 45  │            │ │
│  │  └─────────┘       └─────────┘       └─────────┘             │ │
│  │                                                                 │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  Shard Assignment (via Persistence):                                │
│  • Each shard has exactly ONE owner at a time                       │
│  • Shard ownership tracked in database                              │
│  • On node failure, shards are redistributed                        │
└─────────────────────────────────────────────────────────────────────┘
```

**Shard Count Recommendations / Рекомендации по количеству шардов:**

| Cluster Size | Recommended Shards | Rationale |
|--------------|-------------------|-----------|
| Small (1-3 nodes) | 512 | Default, works for most |
| Medium (4-10 nodes) | 512-1024 | Better distribution |
| Large (10+ nodes) | 2048-4096 | High throughput needs |

**Important:** Shard count is set at cluster creation and cannot be changed without migration.

**Важно:** Количество шардов задаётся при создании кластера и не может быть изменено без миграции.

#### 3. Matching Service / Сервис сопоставления

**Role:** Task routing -- matches workflows/activities to workers.

**Роль:** Маршрутизация задач -- сопоставляет workflow/активности с воркерами.

```
┌─────────────────────────────────────────────────────────────────────┐
│  MATCHING SERVICE                                                   │
│                                                                      │
│  Task Queues:                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  "video-processing"                                          │   │
│  │  ┌────────────────────────────────────────────────────┐     │   │
│  │  │ Task 1 │ Task 2 │ Task 3 │ Task 4 │ ...            │     │   │
│  │  └────────────────────────────────────────────────────┘     │   │
│  │       ▲                                                      │   │
│  │       │ Long Poll                                            │   │
│  │  ┌────┴────┐  ┌─────────┐  ┌─────────┐                     │   │
│  │  │Worker 1 │  │Worker 2 │  │Worker 3 │                     │   │
│  │  └─────────┘  └─────────┘  └─────────┘                     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  "analytics"                                                        │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Task A │ Task B │ ...                                        │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

**Task Queue Properties / Свойства очередей задач:**

- **Sticky Queues:** Workflow tasks prefer returning to the same worker (cache efficiency)
- **Partitioned Queues:** Auto-scaled based on load
- **Priority:** Not native, but achievable via multiple queues

---

## [[Event-Sourcing]] in Temporal / Event Sourcing в Temporal

### How It Works / Как это работает

Temporal uses **Event Sourcing** to persist workflow state. Every action is recorded as an event.

Temporal использует **Event Sourcing** для сохранения состояния workflow. Каждое действие записывается как событие.

```
┌─────────────────────────────────────────────────────────────────────┐
│  WORKFLOW CODE                          EVENT HISTORY               │
│                                                                      │
│  async def process_order(order_id):     ┌──────────────────────┐   │
│      │                                   │ 1. WorkflowStarted   │   │
│      │                                   │    input: order_id   │   │
│      ▼                                   └──────────────────────┘   │
│  payment = await charge_card()          ┌──────────────────────┐   │
│      │                                   │ 2. ActivityScheduled │   │
│      │                                   │    name: charge_card │   │
│      │                                   └──────────────────────┘   │
│      │                                   ┌──────────────────────┐   │
│      │                                   │ 3. ActivityStarted   │   │
│      │                                   └──────────────────────┘   │
│      │                                   ┌──────────────────────┐   │
│      ▼                                   │ 4. ActivityCompleted │   │
│  (payment result received)               │    result: success   │   │
│      │                                   └──────────────────────┘   │
│      ▼                                   ┌──────────────────────┐   │
│  await ship_order()                      │ 5. ActivityScheduled │   │
│      │                                   │    name: ship_order  │   │
│      ...                                 └──────────────────────┘   │
│                                          ...                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Replay Mechanism / Механизм воспроизведения

When a worker needs to continue a workflow (after crash or handoff):

Когда воркеру нужно продолжить workflow (после сбоя или передачи):

```
┌─────────────────────────────────────────────────────────────────────┐
│  REPLAY PROCESS                                                     │
│                                                                      │
│  1. Worker receives task for workflow "order-12345"                 │
│                                                                      │
│  2. Fetch event history from History Service                        │
│     ┌────────────────────────────────────────────────────┐         │
│     │ Event 1: WorkflowStarted                            │         │
│     │ Event 2: ActivityScheduled(charge_card)             │         │
│     │ Event 3: ActivityStarted(charge_card)               │         │
│     │ Event 4: ActivityCompleted(charge_card, success)    │         │
│     │ Event 5: ActivityScheduled(ship_order)              │         │
│     │ Event 6: ActivityStarted(ship_order)                │         │
│     │ Event 7: ActivityCompleted(ship_order, shipped)     │         │
│     │ Event 8: TimerStarted(7 days)                       │         │
│     │ Event 9: TimerFired                                 │ ◄ NOW  │
│     └────────────────────────────────────────────────────┘         │
│                                                                      │
│  3. Re-execute workflow code from beginning                         │
│     ┌────────────────────────────────────────────────────┐         │
│     │ async def process_order(order_id):                  │         │
│     │     payment = await charge_card()                   │         │
│     │     #  ↑ Returns cached result from Event 4         │         │
│     │     await ship_order()                              │         │
│     │     #  ↑ Returns cached result from Event 7         │         │
│     │     await workflow.sleep(days=7)                    │         │
│     │     #  ↑ Timer already fired (Event 9)              │         │
│     │     await send_review_request()  ◄ NEW ACTIVITY    │         │
│     │     #  ↑ Actually schedules new activity            │         │
│     └────────────────────────────────────────────────────┘         │
│                                                                      │
│  4. Only new commands are sent to History Service                   │
│     (ActivityScheduled for send_review_request)                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Determinism Requirement / Требование детерминизма

**Critical:** Workflow code must be deterministic!

**Критически важно:** Код workflow должен быть детерминированным!

```python
# NON-DETERMINISTIC (will break replay)
async def bad_workflow():
    if random.random() > 0.5:      # Different on each replay!
        await do_something()

    current_time = datetime.now()   # Different on each replay!

    data = requests.get(url)        # Network call in workflow!

# DETERMINISTIC (safe for replay)
async def good_workflow():
    # Use workflow.random() for deterministic randomness
    if await workflow.random() > 0.5:
        await do_something()

    # Use workflow.now() for deterministic time
    current_time = workflow.now()

    # External calls go through activities
    data = await fetch_data_activity(url)
```

**Rules for Determinism / Правила детерминизма:**

| Forbidden in Workflow | Use Instead |
|----------------------|-------------|
| `random.random()` | `workflow.random()` |
| `datetime.now()` | `workflow.now()` |
| `time.sleep()` | `workflow.sleep()` |
| `requests.get()` | Activity |
| `os.environ` | Workflow input |
| Global mutable state | Local variables |

---

## Scalability Patterns / Паттерны масштабирования

### Horizontal Scaling / Горизонтальное масштабирование

```
┌─────────────────────────────────────────────────────────────────────┐
│  SCALING TEMPORAL CLUSTER                                           │
│                                                                      │
│  Component        | Scale By           | Bottleneck                 │
│  ─────────────────┼────────────────────┼──────────────────────────  │
│  Frontend Service | Add replicas       | CPU (request processing)   │
│  History Service  | Add replicas       | Shard count (fixed)        │
│  Matching Service | Add replicas       | Task queue partitions      │
│  Worker           | Add replicas       | Activity throughput        │
│  Persistence      | Read replicas,     | Write throughput           │
│                   | sharding           |                            │
└─────────────────────────────────────────────────────────────────────┘
```

### History Service Scaling Limitation / Ограничение масштабирования History Service

```
┌─────────────────────────────────────────────────────────────────────┐
│  SHARD-BASED SCALING LIMIT                                          │
│                                                                      │
│  With 512 shards:                                                   │
│                                                                      │
│  1 node:   512 shards/node = 512 concurrent workflow batches       │
│  4 nodes:  128 shards/node = same total, better distribution       │
│  8 nodes:   64 shards/node = same total, even better               │
│  512 nodes: 1 shard/node = MAXIMUM (can't scale beyond)            │
│                                                                      │
│  Each shard can process ~50-200 workflow tasks/second               │
│  Total cluster: 512 x 100 = ~50,000 workflow tasks/second          │
│                                                                      │
│  Need more? Increase shard count (requires cluster recreation)      │
└─────────────────────────────────────────────────────────────────────┘
```

### Worker Scaling / Масштабирование воркеров

```
┌─────────────────────────────────────────────────────────────────────┐
│  WORKER POOL SCALING                                                │
│                                                                      │
│  Task Queue: "video-processing"                                     │
│                                                                      │
│  Configuration per worker:                                          │
│  • max_concurrent_workflow_task_pollers: 4                         │
│  • max_concurrent_activity_task_pollers: 10                        │
│  • max_concurrent_activities: 100                                   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Worker 1    Worker 2    Worker 3    Worker 4    ...        │   │
│  │  ┌───────┐  ┌───────┐  ┌───────┐  ┌───────┐              │   │
│  │  │ 100   │  │ 100   │  │ 100   │  │ 100   │              │   │
│  │  │ slots │  │ slots │  │ slots │  │ slots │              │   │
│  │  └───────┘  └───────┘  └───────┘  └───────┘              │   │
│  │                                                             │   │
│  │  Total capacity: 4 workers x 100 = 400 concurrent activities│   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Auto-scaling based on:                                             │
│  • Task queue backlog                                               │
│  • Activity execution latency                                       │
│  • Worker CPU/Memory utilization                                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## High Availability / Высокая доступность

### Cluster Topology / Топология кластера

```
┌─────────────────────────────────────────────────────────────────────┐
│  PRODUCTION HA SETUP                                                │
│                                                                      │
│  Zone A               Zone B               Zone C                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐         │
│  │ Frontend x2  │    │ Frontend x2  │    │ Frontend x2  │         │
│  │ History x2   │    │ History x2   │    │ History x2   │         │
│  │ Matching x2  │    │ Matching x2  │    │ Matching x2  │         │
│  │ Worker xN    │    │ Worker xN    │    │ Worker xN    │         │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘         │
│         │                   │                   │                   │
│         └───────────────────┼───────────────────┘                   │
│                             │                                       │
│                      ┌──────┴──────┐                               │
│                      │  Database   │                               │
│                      │  Cluster    │                               │
│                      │ (Primary +  │                               │
│                      │  Replicas)  │                               │
│                      └─────────────┘                               │
└─────────────────────────────────────────────────────────────────────┘
```

### Failure Scenarios / Сценарии отказов

| Failure | Impact | Recovery |
|---------|--------|----------|
| Worker crash | Activity retried on another worker | Automatic, seconds |
| History Service node failure | Shards redistributed | Automatic, ~10 seconds |
| Frontend Service failure | Requests routed to other nodes | Automatic, immediate |
| Database primary failure | Failover to replica | Automatic or manual, depends on setup |
| Network partition | Affected workflows pause | Resume when healed |

---

## Temporal vs Alternatives / Temporal vs Альтернативы

### Comparison Matrix / Матрица сравнения

| Feature | Temporal | Cadence | [[Conductor]] | [[Airflow]] |
|---------|----------|---------|-----------|---------|
| **Paradigm** | Data-centric | Data-centric | Orchestration | Task-centric |
| **State Storage** | Event Sourcing | Event Sourcing | Task status | DAG runs |
| **Languages** | Go, Java, Python, TS, .NET | Go, Java | Any (REST) | Python |
| **Scalability** | History Shards | History Shards | Partitioned queues | Multi-scheduler |
| **Cloud Offering** | Temporal Cloud | None | Netflix (internal) | MWAA, Astronomer |
| **Community** | Very active | Declining | Moderate | Very active |
| **Learning Curve** | High | High | Medium | Medium |

### When to Choose Temporal / Когда выбирать Temporal

**Choose Temporal when / Выбирайте Temporal когда:**
- Long-running workflows (hours/days/weeks)
- Complex branching logic
- Need for durable timers
- Microservice orchestration
- Business-critical processes requiring reliability

**Don't choose Temporal when / Не выбирайте Temporal когда:**
- Simple ETL pipelines (use [[Airflow]])
- Batch processing with fixed schedule
- Team is Python-only with no time to learn
- Low traffic, simple workflows (overkill)

---

## Code Examples / Примеры кода

### Python SDK Example / Пример на Python SDK

```python
from temporalio import workflow, activity
from temporalio.client import Client
from temporalio.worker import Worker
from datetime import timedelta

# Activity definition / Определение активности
@activity.defn
async def process_video(video_id: str) -> dict:
    """External call - can fail, will be retried"""
    # Actual GPU processing here
    return {"status": "processed", "video_id": video_id}

@activity.defn
async def notify_user(user_id: str, message: str) -> None:
    """Send notification"""
    # Email/push notification
    pass

# Workflow definition / Определение workflow
@workflow.defn
class VideoProcessingWorkflow:
    @workflow.run
    async def run(self, video_id: str, user_id: str) -> dict:
        # Step 1: Process video (with retry policy)
        result = await workflow.execute_activity(
            process_video,
            video_id,
            start_to_close_timeout=timedelta(hours=2),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(minutes=10),
                maximum_attempts=5,
            ),
        )

        # Step 2: Wait 1 hour (durable timer - survives crashes)
        await workflow.sleep(timedelta(hours=1))

        # Step 3: Notify user
        await workflow.execute_activity(
            notify_user,
            args=[user_id, f"Video {video_id} is ready!"],
            start_to_close_timeout=timedelta(minutes=1),
        )

        return result

# Starting a workflow / Запуск workflow
async def main():
    client = await Client.connect("localhost:7233")

    # Start workflow
    handle = await client.start_workflow(
        VideoProcessingWorkflow.run,
        args=["video-123", "user-456"],
        id="video-processing-video-123",
        task_queue="video-processing",
    )

    # Wait for result (optional)
    result = await handle.result()
    print(f"Workflow completed: {result}")
```

---

## Monitoring & Observability / Мониторинг и наблюдаемость

### Key Metrics / Ключевые метрики

```
┌─────────────────────────────────────────────────────────────────────┐
│  TEMPORAL METRICS TO MONITOR                                        │
│                                                                      │
│  Cluster Health:                                                    │
│  • temporal_persistence_latency_bucket      (DB latency)           │
│  • temporal_history_shard_controller_*      (Shard distribution)   │
│  • temporal_frontend_*                      (API health)           │
│                                                                      │
│  Workflow Health:                                                   │
│  • temporal_workflow_task_schedule_to_start (Queue wait time)      │
│  • temporal_workflow_task_execution_latency (Processing time)      │
│  • temporal_workflow_failed                 (Failure count)        │
│  • temporal_workflow_completed              (Success count)        │
│                                                                      │
│  Activity Health:                                                   │
│  • temporal_activity_schedule_to_start      (Worker availability)  │
│  • temporal_activity_execution_failed       (Activity failures)    │
│  • temporal_activity_task_timeout           (Timeout rate)         │
│                                                                      │
│  Worker Health:                                                     │
│  • temporal_worker_task_slots_available     (Capacity)             │
│  • temporal_worker_task_slots_used          (Load)                 │
└─────────────────────────────────────────────────────────────────────┘
```

### Temporal Web UI / Веб-интерфейс Temporal

```
┌─────────────────────────────────────────────────────────────────────┐
│  TEMPORAL WEB UI FEATURES                                           │
│                                                                      │
│  • Workflow list with filters (status, type, time range)           │
│  • Workflow detail view:                                            │
│    - Input/output                                                   │
│    - Event history timeline                                         │
│    - Pending activities                                             │
│    - Stack trace (for running workflows)                           │
│  • Query workflows (search by custom attributes)                    │
│  • Terminate/cancel workflows                                       │
│  • Signal workflows                                                 │
│  • Namespace management                                             │
└─────────────────────────────────────────────────────────────────────┘
```

## Связано с
- [[Orchestration]]
- [[Event-Sourcing]]

## Ресурсы
- [Temporal Documentation](https://docs.temporal.io)
- [Temporal Architecture Whitepaper](https://temporal.io/blog/workflow-engine-principles)
- [Temporal GitHub Repository](https://github.com/temporalio/temporal)
- [Temporal Python SDK](https://github.com/temporalio/sdk-python)
- [Designing Distributed Systems with Temporal](https://www.youtube.com/watch?v=2HjnQlnA5eY)
- [Temporal Cluster Scalability](https://docs.temporal.io/clusters)

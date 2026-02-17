---
tags:
  - polyvision
  - system-design
  - orchestration
created: 2026-02-17
---

# Решение по оркестрации Polyvision

## Что это
Архитектурное решение (ADR) для компонента Processing Orchestrator в [[Polyvision]]. Выбран кастомный оркестратор на базе [[Redpanda]] consumer groups + Celery вместо [[Temporal]]/[[Conductor]]/[[Airflow]], так как pipeline линейный и существующая инфраструктура уже покрывает все потребности.

## Problem Statement / Постановка задачи

[[Polyvision]] needs to orchestrate a **multi-stage video processing pipeline**:

```
Upload → Stitch → Detect → Track → VCam + Analyze → Encode → Ready
```

**Requirements / Требования:**

| Requirement (EN) | Требование (RU) | Priority |
|------------------|-----------------|----------|
| Process ~32 min for 90-min match | Обработка ~32 мин на 90-мин матч | High |
| Handle failures with retry | Обработка сбоев с повторами | High |
| Track progress (UI updates) | Отслеживание прогресса (для UI) | High |
| Support reprocessing (new model) | Поддержка переобработки | Medium |
| Scale horizontally | Горизонтальное масштабирование | Medium |
| No single point of failure | Отсутствие SPOF | High |

---

## Alternatives Considered / Рассмотренные альтернативы

### Alternative 1: Apache [[Airflow]]

```
┌─────────────────────────────────────────────────────────────────────┐
│  AIRFLOW APPROACH                                                    │
│                                                                      │
│  DAG Definition:                                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  with DAG("video_processing") as dag:                        │   │
│  │      ingest = PythonOperator(task_id="ingest")               │   │
│  │      stitch = KubernetesOperator(task_id="stitch")          │   │
│  │      detect = KubernetesOperator(task_id="detect")          │   │
│  │      ...                                                      │   │
│  │      ingest >> stitch >> detect >> [vcam, analyze] >> encode │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Architecture:                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Scheduler 1  │  │ Scheduler 2  │  │  PostgreSQL  │              │
│  │  (active)    │  │   (active)   │  │  (metadata)  │              │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘              │
│         │                 │                                         │
│         └────────┬────────┘                                         │
│                  │ SELECT ... FOR UPDATE SKIP LOCKED                │
│                  ▼                                                   │
│         ┌──────────────────────────────────────────┐                │
│         │          Celery Workers (GPU)             │                │
│         └──────────────────────────────────────────┘                │
└─────────────────────────────────────────────────────────────────────┘
```

**Pros / Плюсы:**
- Mature ecosystem, large community / Зрелая экосистема, большое сообщество
- Python-native (fits our stack) / Нативный Python
- Good UI for DAG visualization / Хороший UI для визуализации
- Easy to get started / Легко начать

**Cons / Минусы:**
- Designed for batch, not event-driven / Для пакетной обработки, не событийной
- DB-based coordination adds latency / Координация через БД добавляет латентность
- Not ideal for long-running (hours) tasks / Не идеально для долгих задач
- DAG definitions are static / Определения DAG статичны

**Verdict:** Not chosen. Batch-oriented design doesn't fit our event-driven needs.

---

### Alternative 2: [[Temporal]].io

```
┌─────────────────────────────────────────────────────────────────────┐
│  TEMPORAL APPROACH                                                   │
│                                                                      │
│  Workflow Code:                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  @workflow.defn                                              │   │
│  │  class VideoProcessingWorkflow:                              │   │
│  │      @workflow.run                                           │   │
│  │      async def run(self, match_id: str):                    │   │
│  │          await workflow.execute_activity(ingest, match_id)  │   │
│  │          await workflow.execute_activity(stitch, match_id)  │   │
│  │          await workflow.execute_activity(detect, match_id)  │   │
│  │          await asyncio.gather(                               │   │
│  │              workflow.execute_activity(vcam, match_id),     │   │
│  │              workflow.execute_activity(analyze, match_id)   │   │
│  │          )                                                   │   │
│  │          await workflow.execute_activity(encode, match_id)  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Architecture:                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                 TEMPORAL CLUSTER                              │   │
│  │   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │   │
│  │   │Frontend │  │ History │  │Matching │  │ Worker  │        │   │
│  │   │ Service │  │ Service │  │ Service │  │ Service │        │   │
│  │   └─────────┘  └─────────┘  └─────────┘  └─────────┘        │   │
│  │        │            │            │            │               │   │
│  │        └────────────┴────────────┴────────────┘               │   │
│  │                          │                                     │   │
│  │                    ┌─────────────┐                             │   │
│  │                    │ Cassandra/  │                             │   │
│  │                    │ PostgreSQL  │                             │   │
│  │                    └─────────────┘                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  + Our Workers                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │   │
│  │  │ Stitch  │  │ Detect  │  │  VCam   │  │ Encode  │        │   │
│  │  │ Worker  │  │ Worker  │  │ Worker  │  │ Worker  │        │   │
│  │  │  (GPU)  │  │  (GPU)  │  │  (GPU)  │  │  (GPU)  │        │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘        │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

**Pros / Плюсы:**
- Durable execution (survives failures) / Устойчивое выполнение
- Write workflows as code / Workflow как код
- Built-in retry, timeout handling / Встроенные retry и timeout
- Excellent for long-running workflows / Отлично для долгих workflow
- Scalable via History Shards / Масштабируется через History Shards

**Cons / Минусы:**
- Additional infrastructure ([[Temporal]] cluster) / Дополнительная инфраструктура
- Steeper learning curve / Более крутая кривая обучения
- Overkill for simpler use cases / Избыточно для простых случаев
- Resource-intensive cluster / Ресурсоёмкий кластер

**Verdict:** Strong candidate, but adds operational complexity.

---

### Alternative 3: Netflix [[Conductor]]

```
┌─────────────────────────────────────────────────────────────────────┐
│  CONDUCTOR APPROACH                                                  │
│                                                                      │
│  JSON Workflow Definition:                                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  {                                                           │   │
│  │    "name": "video_processing",                              │   │
│  │    "tasks": [                                               │   │
│  │      {"name": "ingest", "type": "SIMPLE"},                 │   │
│  │      {"name": "stitch", "type": "SIMPLE"},                 │   │
│  │      {"name": "detect", "type": "SIMPLE"},                 │   │
│  │      {                                                       │   │
│  │        "type": "FORK_JOIN",                                 │   │
│  │        "forkTasks": [["vcam"], ["analyze"]]                │   │
│  │      },                                                      │   │
│  │      {"name": "encode", "type": "SIMPLE"}                  │   │
│  │    ]                                                         │   │
│  │  }                                                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Pros:                            Cons:                             │
│  • Visual UI                      • JSON workflows less flexible    │
│  • Lightweight                    • Less mature than Temporal       │
│  • Good for ops visibility        • Smaller community               │
└─────────────────────────────────────────────────────────────────────┘
```

**Verdict:** Good for visibility, but JSON-based workflows are limiting.

---

### Alternative 4: Custom Orchestrator (Chosen)

```
┌─────────────────────────────────────────────────────────────────────┐
│  POLYVISION CUSTOM ORCHESTRATOR                                      │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │               polyvision.jobs.commands (12 partitions)       │   │
│  │   ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐   │   │
│  │   │ P0  │ P1  │ P2  │ P3  │ P4  │ P5  │ P6  │ P7  │ ... │   │   │
│  │   └──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴─────┘   │   │
│  │      │     │     │     │     │     │     │     │             │   │
│  │      └─────┼─────┴─────┼─────┴─────┼─────┴─────┘             │   │
│  │            │           │           │                          │   │
│  │            ▼           ▼           ▼                          │   │
│  │   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │   │
│  │   │Orchestrator │ │Orchestrator │ │Orchestrator │            │   │
│  │   │   Pod 1     │ │   Pod 2     │ │   Pod 3     │            │   │
│  │   └─────────────┘ └─────────────┘ └─────────────┘            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                │                                    │
│                                ▼                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    CELERY TASK QUEUES                         │   │
│  │                                                               │   │
│  │   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │   │
│  │   │ stitch  │  │ detect  │  │  vcam   │  │ encode  │        │   │
│  │   │  queue  │  │  queue  │  │  queue  │  │  queue  │        │   │
│  │   └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘        │   │
│  │        │            │            │            │               │   │
│  │        ▼            ▼            ▼            ▼               │   │
│  │   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │   │
│  │   │ Stitch  │  │ Detect  │  │  VCam   │  │ Encode  │        │   │
│  │   │ Worker  │  │ Worker  │  │ Worker  │  │ Worker  │        │   │
│  │   │  (GPU)  │  │  (GPU)  │  │  (GPU)  │  │ (NVENC) │        │   │
│  │   └─────────┘  └─────────┘  └─────────┘  └─────────┘        │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                │                                    │
│                                ▼                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      DATA STORES                              │   │
│  │   ┌───────────┐  ┌───────────┐  ┌───────────┐               │   │
│  │   │PostgreSQL │  │  Redis    │  │ ClickHouse│               │   │
│  │   │(job state)│  │(idempot.) │  │(detections│               │   │
│  │   └───────────┘  └───────────┘  └───────────┘               │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

**Verdict:** CHOSEN. Fits our needs without additional infrastructure.

---

## Why Custom Orchestrator? / Почему кастомный оркестратор?

### 1. We Already Have the Pieces / У нас уже есть компоненты

| Component | What We Have | What [[Temporal]] Would Add |
|-----------|--------------|-------------------------|
| Event bus | [[Redpanda]] | Temporal cluster |
| Task queue | Celery + Redis | Temporal workers |
| State storage | PostgreSQL | Cassandra/PostgreSQL |
| Workers | GPU workers | Need to integrate anyway |

**[[Temporal]] would add 4 new services** (Frontend, History, Matching, Worker) while we already have equivalents.

### 2. Our Workflows Are Simple / Наши workflow простые

```
┌─────────────────────────────────────────────────────────────────────┐
│  POLYVISION WORKFLOW COMPLEXITY                                      │
│                                                                      │
│  Typical Temporal use case:              Our use case:              │
│                                                                      │
│  ┌────────────────────────┐             ┌────────────────────────┐ │
│  │ Order → Payment →      │             │ Stitch → Detect →      │ │
│  │   ├─ if failed: retry  │             │   Track → VCam/Analyze │ │
│  │   ├─ if blocked: wait  │             │     → Encode           │ │
│  │   └─ human approval    │             │                        │ │
│  │ → Shipping → Review    │             │ Linear with one fork   │ │
│  │   ├─ wait 7 days       │             │ No human interaction   │ │
│  │   └─ send email        │             │ No long waits          │ │
│  │ Complex branching      │             │ Simple pipeline        │ │
│  └────────────────────────┘             └────────────────────────┘ │
│                                                                      │
│  Temporal excels at:                    We don't need:             │
│  • Complex branching                    • Complex branching        │
│  • Human-in-loop                        • Human-in-loop           │
│  • Multi-day workflows                  • Multi-day waits         │
│  • Dynamic workflow changes             • Dynamic changes         │
└─────────────────────────────────────────────────────────────────────┘
```

### 3. Operational Simplicity / Операционная простота

| Metric | Custom | [[Temporal]] |
|--------|--------|----------|
| New services to manage | 0 | 4 |
| New databases | 0 | 1 (Cassandra recommended) |
| Team learning curve | Low | High |
| Debugging complexity | Familiar tools | New concepts |

---

## Architecture Deep Dive / Глубокое погружение в архитектуру

### Orchestrator HA Pattern: Partitioned Load Distribution

**Key insight:** We chose **[[Temporal]]-style partitioning** but implemented with our existing [[Redpanda]] infrastructure.

```
┌─────────────────────────────────────────────────────────────────────┐
│  PARTITIONED LOAD DISTRIBUTION (Temporal-style)                      │
│                                                                      │
│  NOT Leader Election:                                               │
│  ├── Both pods actively process jobs                                │
│  ├── Work divided by partition (hash of match_id)                   │
│  └── Similar to Temporal History Shards concept                     │
│                                                                      │
│  Partition Key: {organization_id}:{match_id}                        │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  polyvision.jobs.commands topic (12 partitions)              │   │
│  │                                                               │   │
│  │  hash("org-1:match-A") % 12 = 3 → Partition 3                │   │
│  │  hash("org-1:match-B") % 12 = 7 → Partition 7                │   │
│  │  hash("org-2:match-C") % 12 = 3 → Partition 3                │   │
│  │                                                               │   │
│  │  Consumer Group: "orchestrator"                               │   │
│  │  ┌──────────────────────────────────────────────────────┐    │   │
│  │  │  Orchestrator Pod 1: Partitions 0,1,2,3,4,5          │    │   │
│  │  │  Orchestrator Pod 2: Partitions 6,7,8,9,10,11        │    │   │
│  │  └──────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Benefits:                                                           │
│  ├── All events for one match → same orchestrator pod               │
│  ├── Ordering guaranteed within partition                           │
│  ├── Cache locality for match state                                 │
│  └── On pod failure: Redpanda rebalances partitions automatically   │
└─────────────────────────────────────────────────────────────────────┘
```

### Comparison with Industry / Сравнение с индустрией

| System | Approach | Our Equivalent |
|--------|----------|----------------|
| **[[Temporal]]** | History Shards (hash of workflow_id) | [[Redpanda]] partitions (hash of match_id) |
| **Cadence** | Sharded History Service | Same concept |
| **[[Conductor]]** | Partitioned task queues | Celery queues per stage |
| **[[Airflow]] 2.x** | DB row locking (`FOR UPDATE SKIP LOCKED`) | Could use, but adds latency |

---

## [[Idempotency]] Implementation / Реализация идемпотентности

Critical for handling duplicate messages during rebalancing:

```python
@shared_task(
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=3
)
def process_stage(self, job_id: str, match_id: str, stage: str):
    """
    Idempotent stage processing.

    Key format: {stage}:{organization_id}:{match_id}:{model_version}
    """
    model_version = get_current_model_version() if stage == "detect" else "default"
    idempotency_key = f"{stage}:{organization_id}:{match_id}:{model_version}"

    # Atomic check-and-set
    if not redis.setnx(idempotency_key, "processing"):
        status = redis.get(idempotency_key)
        if status == b"completed":
            logger.info(f"Skipping duplicate: {idempotency_key}")
            return {"status": "already_processed"}
        elif status == b"processing":
            # Another worker handling - retry later
            raise self.retry(countdown=60)

    try:
        redis.expire(idempotency_key, 7200)  # 2h TTL while processing

        # Actual processing
        result = execute_stage(stage, match_id)

        redis.setex(idempotency_key, 86400 * 7, "completed")  # 7 days
        return result

    except Exception as e:
        redis.delete(idempotency_key)  # Allow retry
        raise
```

---

## Failover Behavior / Поведение при сбоях

| Scenario | Recovery Time | Data Loss | Action |
|----------|---------------|-----------|--------|
| Pod crash | ~10 seconds | None | [[Redpanda]] consumer group rebalance |
| Node failure | ~30 seconds | None | K8s reschedule + rebalance |
| Network partition | Consumer timeout | None | At-least-once + [[Idempotency]] |
| Database failure | Service degraded | None | Jobs queued in [[Redpanda]] |

---

## Trade-offs / Компромиссы

### What We Gain / Что получаем

| Benefit | Details |
|---------|---------|
| **Operational simplicity** | No new infrastructure to learn/maintain |
| **Cost efficiency** | Use existing [[Redpanda]], Redis, PostgreSQL |
| **Team velocity** | Familiar tools, faster development |
| **Flexibility** | Full control over orchestration logic |

### What We Sacrifice / Чем жертвуем

| Sacrifice | Mitigation |
|-----------|------------|
| **No durable execution** | [[Idempotency]] + job state in PostgreSQL |
| **No visual workflow editor** | Document workflows in code |
| **No built-in versioning** | Manual workflow version management |
| **More custom code** | Well-tested patterns from Celery ecosystem |

---

## When to Reconsider / Когда пересмотреть

Consider migrating to [[Temporal]] if:

1. **Workflow complexity increases** -- need complex branching, human-in-loop
2. **Multi-day workflows** -- need durable timers (wait 7 days, send email)
3. **Team grows** -- benefits of [[Temporal]] outweigh learning curve
4. **Debugging becomes hard** -- [[Temporal]]'s history replay is powerful

---

## Interview Questions / Вопросы для интервью

**Q: Why didn't you use [[Temporal]] for orchestration?**

A: We evaluated [[Temporal]] and found it's an excellent solution, but it adds operational complexity (4 new services, new database) for our relatively simple pipeline. Our workflows are linear with one fork point, no human interaction, and process in ~32 minutes. We implemented [[Temporal]]-style partitioned load distribution using our existing [[Redpanda]] infrastructure, achieving similar scalability benefits without additional infrastructure.

**Q: How do you handle orchestrator failures?**

A: We use [[Redpanda]] consumer groups for partition-based load distribution. When an orchestrator pod fails, [[Redpanda]] automatically rebalances partitions to surviving pods within ~10 seconds. All job state is in PostgreSQL, and [[Idempotency]] keys in Redis prevent duplicate processing during rebalancing.

**Q: What's your partition key strategy?**

A: We use `{organization_id}:{match_id}` as the partition key. This ensures:
1. All events for a match go to the same orchestrator pod (ordering)
2. Tenant locality (all jobs for an org tend to go to same pods)
3. Even distribution across partitions (good hash distribution)

## Связано с
- [[Polyvision]]
- [[Orchestration]]
- [[Temporal]]
- [[Redpanda]]

## Ресурсы
- [Temporal Documentation: History Shards](https://docs.temporal.io/temporal-service/temporal-server#history-shard)
- [Redpanda Consumer Groups](https://www.redpanda.com/guides/kafka-architecture-kafka-consumer-group)
- [Celery Task Best Practices](https://docs.celeryq.dev/en/stable/userguide/tasks.html)

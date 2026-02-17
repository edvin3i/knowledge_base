---
tags:
  - polyvision
  - system-design
  - high-availability
created: 2026-02-17
---

# Polyvision High Availability Decision: Orchestrator HA
# Решение по высокой доступности Polyvision: HA оркестратора

> **Context:** This document captures our architectural decision (Q1) for Orchestrator High Availability.
>
> **Контекст:** Этот документ фиксирует наше архитектурное решение (Q1) по высокой доступности оркестратора.

## Что это

Архитектурное решение [[Polyvision]] по обеспечению высокой доступности Processing Orchestrator через партиционированное распределение нагрузки на базе [[Redpanda]] consumer groups. Анализ альтернатив (Leader Election, Active-Passive), реализация идемпотентности при ребалансировке, сценарии сбоев.

---

## Problem Statement / Постановка задачи

The Processing Orchestrator is a critical component that:
- Receives job commands from [[Redpanda]]
- Creates Celery tasks for GPU workers
- Tracks job state and progress
- Coordinates stage transitions

**Single orchestrator = SPOF (Single Point of Failure)**

```
┌─────────────────────────────────────────────────────────────────────┐
│  THE PROBLEM: SINGLE POINT OF FAILURE                                │
│                                                                      │
│                 ┌──────────────────┐                                │
│                 │   Orchestrator   │ ← If this dies, no new jobs    │
│                 │     (SINGLE)     │   are processed                │
│                 └────────┬─────────┘                                │
│                          │                                          │
│       ┌──────────────────┼──────────────────┐                       │
│       ▼                  ▼                  ▼                       │
│  ┌─────────┐        ┌─────────┐        ┌─────────┐                 │
│  │ Worker 1│        │ Worker 2│        │ Worker 3│                 │
│  └─────────┘        └─────────┘        └─────────┘                 │
│                                                                      │
│  Impact:                                                             │
│  • New uploads not processed                                        │
│  • In-progress jobs may stall                                       │
│  • Users see no progress updates                                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Requirements / Требования

| Requirement (EN) | Требование (RU) | Target |
|------------------|-----------------|--------|
| Failover time | Время переключения | < 30 seconds |
| Data loss | Потеря данных | None (RPO = 0) |
| In-flight job handling | Обработка текущих задач | Resume, not restart |
| Horizontal scalability | Горизонтальное масштабирование | Support 2-6 pods |
| Operational simplicity | Операционная простота | No new infrastructure |

---

## Alternatives Considered / Рассмотренные альтернативы

### Alternative A: True Leader Election

**Concept:** Only one pod processes all jobs, others are standby.

```
┌─────────────────────────────────────────────────────────────────────┐
│  LEADER ELECTION                                                     │
│                                                                      │
│  ┌───────────────────┐         ┌───────────────────┐               │
│  │  Orchestrator 1   │         │  Orchestrator 2   │               │
│  │   (LEADER ✓)      │         │   (STANDBY)       │               │
│  │                   │         │                   │               │
│  │ • Processes ALL   │         │ • Heartbeat only  │               │
│  │   jobs            │         │ • Ready to take   │               │
│  │ • Single stream   │         │   over            │               │
│  └───────────────────┘         └───────────────────┘               │
│                                                                      │
│  Implementation options:                                             │
│  1. Kubernetes Lease API                                            │
│  2. Redis SETNX with TTL                                            │
│  3. Redpanda single-partition topic                                 │
│  4. ZooKeeper/etcd                                                  │
└─────────────────────────────────────────────────────────────────────┘
```

**Pros / Плюсы:**
- Simple mental model / Простая ментальная модель
- No partition coordination / Нет координации партиций
- Clear "who owns what" / Понятно "кто чем владеет"

**Cons / Минусы:**
- Standby resources wasted / Ресурсы standby не используются
- Throughput limited by single pod / Throughput ограничен одним pod'ом
- Failover requires leader re-election / Failover требует перевыборов

**Verdict:** Not scalable. Wastes resources. Throughput bottleneck.

---

### Alternative B: Active-Passive with Shared State

**Concept:** One active pod, one passive. Passive monitors active via heartbeat.

```
┌─────────────────────────────────────────────────────────────────────┐
│  ACTIVE-PASSIVE                                                      │
│                                                                      │
│  ┌───────────────────┐         ┌───────────────────┐               │
│  │  Orchestrator 1   │         │  Orchestrator 2   │               │
│  │   (ACTIVE)        │         │   (PASSIVE)       │               │
│  │                   │         │                   │               │
│  │ • Processes jobs  │ ──────► │ • Monitors health │               │
│  │ • Writes state    │heartbeat│ • Takes over on   │               │
│  │                   │         │   failure         │               │
│  └─────────┬─────────┘         └─────────┬─────────┘               │
│            │                             │                          │
│            └──────────┬──────────────────┘                          │
│                       ▼                                             │
│              ┌─────────────────┐                                    │
│              │  Redis (state)  │                                    │
│              └─────────────────┘                                    │
└─────────────────────────────────────────────────────────────────────┘
```

**Pros / Плюсы:**
- Clear active/passive roles / Чёткие роли active/passive
- Simpler than full load distribution / Проще чем распределение нагрузки

**Cons / Минусы:**
- Still wastes standby resources / Всё ещё тратит ресурсы standby
- Split-brain risk / Риск split-brain
- Doesn't scale beyond 2 pods / Не масштабируется выше 2 pod'ов

**Verdict:** Not scalable. Split-brain risk.

---

### Alternative C: Partitioned Load Distribution (Temporal-style) -- CHOSEN

**Concept:** Multiple active pods, each owns partitions. Work distributed by partition key.

```
┌─────────────────────────────────────────────────────────────────────┐
│  PARTITIONED LOAD DISTRIBUTION                                       │
│                                                                      │
│  polyvision.jobs.commands (12 partitions)                           │
│  ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬────┐│
│  │ P0  │ P1  │ P2  │ P3  │ P4  │ P5  │ P6  │ P7  │ P8  │ P9  │... ││
│  └──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴────┘│
│     │     │     │     │     │     │     │     │     │     │        │
│     └─────┼─────┘     └─────┼─────┘     └─────┼─────┘     │        │
│           │                 │                 │           │        │
│           ▼                 ▼                 ▼           ▼        │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐  (can add)   │
│  │Orchestrator │   │Orchestrator │   │Orchestrator │              │
│  │   Pod 1     │   │   Pod 2     │   │   Pod 3     │              │
│  │ P0,P3,P6,P9 │   │ P1,P4,P7,P10│   │ P2,P5,P8,P11│              │
│  └─────────────┘   └─────────────┘   └─────────────┘              │
│                                                                      │
│  All pods ACTIVE. Work divided by partition.                        │
└─────────────────────────────────────────────────────────────────────┘
```

**Pros / Плюсы:**
- All pods actively working / Все pod'ы активно работают
- Scales horizontally (add pods <= partitions) / Масштабируется горизонтально
- Automatic rebalancing on failure / Автоматическая ребалансировка при сбое
- Industry-proven pattern (Temporal, Kafka) / Проверенный индустрией паттерн

**Cons / Минусы:**
- Slightly more complex / Немного сложнее
- Need idempotency for rebalancing / Нужна идемпотентность для ребалансировки
- Partition count limits max pods / Число партиций ограничивает макс. pod'ов

**Verdict:** CHOSEN. Best balance of scalability, efficiency, and industry alignment.

---

## Why Partitioned Load Distribution? / Почему партиционированное распределение?

### Industry Alignment / Соответствие индустрии

| System | Approach | How it works |
|--------|----------|--------------|
| **Temporal** | History Shards | `hash(workflow_id) % num_shards` |
| **Uber Cadence** | Sharded History | Same as Temporal |
| **Apache Kafka** | Consumer Groups | `hash(key) % partitions` |
| **Netflix Conductor** | Partitioned Queues | Per-task-type queues |
| **Airflow 2.x** | DB Row Locking | `FOR UPDATE SKIP LOCKED` |

**Our choice aligns with Temporal/Kafka patterns** -- proven at scale.

### Why Not Airflow-style DB Locking?

```
┌─────────────────────────────────────────────────────────────────────┐
│  AIRFLOW-STYLE (DB Locking)                                          │
│                                                                      │
│  Each scheduler:                                                     │
│  SELECT * FROM dag_run                                              │
│  WHERE state = 'queued'                                             │
│  FOR UPDATE SKIP LOCKED                                             │
│  LIMIT 10;                                                          │
│                                                                      │
│  Pros:                          Cons:                               │
│  • Simple to implement          • Database bottleneck               │
│  • No partition planning        • +5-10ms latency per lock          │
│  • Works with any DB            • Scales to ~10 schedulers max      │
│                                 • Contention under high load        │
└─────────────────────────────────────────────────────────────────────┘
```

We chose [[Redpanda]] partitions over DB locking because:
1. We already have Redpanda / У нас уже есть Redpanda
2. No additional latency / Нет дополнительной латентности
3. Better scalability / Лучшая масштабируемость

---

## Implementation Details / Детали реализации

### Partition Key Strategy

```python
# Producer: publish with partition key
await redpanda.publish(
    topic="polyvision.jobs.commands",
    key=f"{organization_id}:{match_id}",  # Partition key
    value=job_command
)
```

**Why `{organization_id}:{match_id}`?**

| Benefit | Explanation |
|---------|-------------|
| **Ordering** | All events for match go to same partition -> same pod |
| **Tenant locality** | Jobs for same org tend to same pods -> better caching |
| **Even distribution** | Good hash distribution across partitions |

### Consumer Configuration

```python
consumer = AIOKafkaConsumer(
    "polyvision.jobs.commands",
    bootstrap_servers=REDPANDA_BROKERS,
    group_id="polyvision-orchestrator",  # Consumer group
    auto_offset_reset="earliest",
    enable_auto_commit=False,  # Manual commit for reliability
)
```

### Idempotency for Rebalancing

During rebalancing, messages may be redelivered. [[Idempotency]] prevents duplicates:

```python
async def handle_job_command(message):
    job_id = message.value["job_id"]
    idempotency_key = f"job:processed:{job_id}"

    # Check if already processed
    if await redis.get(idempotency_key):
        logger.info(f"Skipping duplicate job: {job_id}")
        return

    # Process job
    await create_celery_tasks(job_id)

    # Mark as processed (7-day TTL)
    await redis.setex(idempotency_key, 86400 * 7, "1")

    # Commit offset
    await consumer.commit()
```

---

## Failover Scenarios / Сценарии сбоев

### Scenario 1: Pod Crash

```
┌─────────────────────────────────────────────────────────────────────┐
│  POD CRASH FAILOVER                                                  │
│                                                                      │
│  T=0: Normal operation                                              │
│  ┌─────────────┐   ┌─────────────┐                                 │
│  │   Pod 1     │   │   Pod 2     │                                 │
│  │ P0,P1,P2,P3 │   │ P4,P5,P6,P7 │                                 │
│  └─────────────┘   └─────────────┘                                 │
│                                                                      │
│  T=1: Pod 1 crashes                                                 │
│  ┌─────────────┐   ┌─────────────┐                                 │
│  │   Pod 1     │   │   Pod 2     │                                 │
│  │    ❌        │   │ P4,P5,P6,P7 │                                 │
│  └─────────────┘   └─────────────┘                                 │
│                                                                      │
│  T=2: Redpanda detects (session.timeout.ms ~10s)                   │
│                                                                      │
│  T=3: Rebalance triggered                                           │
│  ┌─────────────┐   ┌───────────────────────┐                       │
│  │   Pod 1     │   │        Pod 2          │                       │
│  │    ❌        │   │ P0,P1,P2,P3,P4,P5,P6,P7 │                      │
│  └─────────────┘   └───────────────────────┘                       │
│                                                                      │
│  Pod 2 now owns ALL partitions                                      │
│  Uncommitted messages from Pod 1 will be redelivered                │
│  Idempotency prevents duplicate processing                          │
└─────────────────────────────────────────────────────────────────────┘

Recovery time: ~10 seconds
Data loss: None (uncommitted messages redelivered)
```

### Scenario 2: Network Partition

```
┌─────────────────────────────────────────────────────────────────────┐
│  NETWORK PARTITION                                                   │
│                                                                      │
│  Pod 1 loses connection to Redpanda                                 │
│                                                                      │
│  1. Pod 1 stops receiving heartbeat responses                       │
│  2. Redpanda marks Pod 1 as dead after session.timeout.ms           │
│  3. Partitions reassigned to Pod 2                                  │
│  4. Pod 1 eventually detects it's no longer leader                  │
│  5. Pod 1 stops processing (commits will fail)                      │
│                                                                      │
│  No split-brain: Only the pod that can commit is processing         │
└─────────────────────────────────────────────────────────────────────┘

Recovery time: ~10-30 seconds
Data loss: None
```

### Scenario 3: Rolling Update

```
┌─────────────────────────────────────────────────────────────────────┐
│  ROLLING UPDATE (ZERO DOWNTIME)                                      │
│                                                                      │
│  1. K8s signals Pod 1 to terminate (SIGTERM)                        │
│  2. Pod 1 stops consuming, commits current offsets                  │
│  3. Pod 1 leaves consumer group gracefully                          │
│  4. Redpanda rebalances partitions to Pod 2                         │
│  5. New Pod 1 starts, joins consumer group                          │
│  6. Partitions rebalanced again                                     │
│                                                                      │
│  preStop hook ensures graceful shutdown:                            │
│  lifecycle:                                                          │
│    preStop:                                                          │
│      exec:                                                           │
│        command: ["sh", "-c", "sleep 5"]  # Allow in-flight commits │
└─────────────────────────────────────────────────────────────────────┘

Recovery time: 0 (graceful handoff)
Data loss: None
```

---

## Monitoring / Мониторинг

Key metrics to track:

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `consumer_lag` | Messages behind head | > 1000 for 5 min |
| `rebalance_count` | Rebalances per hour | > 5 |
| `job_processing_time` | P99 job duration | > 2x baseline |
| `idempotency_hits` | Duplicate detections | > 10% |

---

## Trade-offs / Компромиссы

### What We Gain / Что получаем

| Benefit | Details |
|---------|---------|
| **High Availability** | No SPOF, automatic failover |
| **Horizontal Scalability** | Add pods up to partition count |
| **Resource Efficiency** | All pods actively working |
| **Industry Alignment** | Same pattern as Temporal |

### What We Accept / Что принимаем

| Trade-off | Mitigation |
|-----------|------------|
| **Rebalancing complexity** | Idempotency handles duplicates |
| **Partition count limits max pods** | 12 partitions = up to 12 pods (plenty) |
| **Not true HA for single job** | Job state in PostgreSQL survives pod death |

---

## Interview Questions / Вопросы для интервью

**Q: Why did you choose partitioned load distribution over leader election?**

A: Leader election wastes resources (standby pod does nothing) and creates a throughput bottleneck (single pod processes everything). Partitioned load distribution uses all pods actively, scales horizontally, and aligns with industry patterns like Temporal's History Shards. On failover, Redpanda's consumer group rebalancing automatically redistributes partitions.

**Q: How do you prevent duplicate processing during rebalancing?**

A: We implement idempotency at the job level. Each job command has a unique ID. Before processing, we check Redis for an idempotency key. If present, we skip. After successful processing, we set the key with a 7-day TTL. This ensures at-least-once delivery semantics are effectively exactly-once from the application perspective.

**Q: What happens to in-flight jobs when a pod crashes?**

A: Job state is stored in PostgreSQL, not in the pod's memory. When a pod crashes:
1. Uncommitted Redpanda messages are redelivered to another pod
2. Idempotency prevents re-processing of already-completed steps
3. Celery tasks continue executing on GPU workers
4. The new orchestrator pod picks up from the last committed state

## Связано с

- [[Polyvision]]
- [[HA-Patterns]]
- [[Redpanda]]
- [[Consensus]]

## Ресурсы

- [Kafka Consumer Groups](https://kafka.apache.org/documentation/#consumerconfigs)
- [Redpanda Consumer Offsets](https://docs.redpanda.com/current/develop/consume-data/consumer-offsets/)
- [Temporal History Shards](https://docs.temporal.io/temporal-service/temporal-server#history-shard)
- [Kafka Rebalancing Deep Dive](https://www.redpanda.com/guides/kafka-performance-kafka-rebalancing)

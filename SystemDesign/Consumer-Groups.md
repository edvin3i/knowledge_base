---
tags:
  - system-design
  - kafka
  - consumer-groups
created: 2026-02-17
---

# Consumer-группы в Kafka

## Что это
Consumer Group -- набор потребителей, совместно обрабатывающих сообщения из топика [[Kafka]]. Каждая партиция назначается ровно одному потребителю в группе. Ключевой механизм горизонтального масштабирования потребления. Включает стратегии назначения (Range, Round-Robin, Sticky, Cooperative Sticky) и ребалансировку.

## What is a Consumer Group? / Что такое Consumer Group?

A **Consumer Group** is a set of consumers that cooperatively consume messages from a topic. Each partition is assigned to exactly one consumer within the group.

**Consumer Group** -- это набор потребителей, совместно обрабатывающих сообщения из топика. Каждая партиция назначается ровно одному потребителю в группе.

### Core Principle / Основной принцип

```
┌─────────────────────────────────────────────────────────────────────┐
│  CONSUMER GROUP PARTITION ASSIGNMENT                                │
│                                                                      │
│  Topic: orders (6 partitions)                                       │
│  Consumer Group: order-processors                                   │
│                                                                      │
│  ┌─────┬─────┬─────┬─────┬─────┬─────┐                            │
│  │ P0  │ P1  │ P2  │ P3  │ P4  │ P5  │                            │
│  └──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴──┬──┘                            │
│                       ▼   ▼   ▼   ▼   ▼   ▼                        │
│                    ┌─────────────────────────┐                     │
│                    │ Consumer 1: P0, P1      │                     │
│                    │ Consumer 2: P2, P3      │                     │
│                    │ Consumer 3: P4, P5      │                     │
│                    └─────────────────────────┘                     │
│                                                                      │
│  Rules:                                                             │
│  • Each partition → exactly 1 consumer                             │
│  • Each consumer → 0 or more partitions                            │
│  • If consumers > partitions → some consumers idle                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Scaling Consumers / Масштабирование потребителей

### Consumer Count vs Partition Count / Количество Consumer vs Количество партиций

```
┌─────────────────────────────────────────────────────────────────────┐
│  SCALING SCENARIOS                                                  │
│                                                                      │
│  Topic: 6 partitions                                                │
│                                                                      │
│  1 Consumer:  [Consumer 1] handles all 6                           │
│  3 Consumers: 2 partitions each                                    │
│  6 Consumers: 1 partition each (optimal)                           │
│  8 Consumers: 6 active + 2 IDLE (wasted resources!)               │
└─────────────────────────────────────────────────────────────────────┘
```

### Multiple Consumer Groups / Несколько Consumer Groups

```
┌─────────────────────────────────────────────────────────────────────┐
│  INDEPENDENT CONSUMER GROUPS                                        │
│                                                                      │
│  Topic: orders (4 partitions)                                       │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐                                  │
│  │ Group A     │  │ Group B     │                                  │
│  │ "analytics" │  │ "billing"   │                                  │
│  │             │  │             │                                  │
│  │ C1: P0,P1   │  │ C1: P0,P1   │                                  │
│  │ C2: P2,P3   │  │ C2: P2,P3   │                                  │
│  └─────────────┘  └─────────────┘                                  │
│                                                                      │
│  Each group gets ALL messages independently!                       │
│  Use case: Same data, different processing                         │
│  • Group A: Calculate metrics                                      │
│  • Group B: Generate invoices                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Rebalancing / Ребалансировка

### What Triggers Rebalancing / Что вызывает ребалансировку

```
┌─────────────────────────────────────────────────────────────────────┐
│  REBALANCE TRIGGERS                                                 │
│                                                                      │
│  1. Consumer joins group                                            │
│  2. Consumer leaves group (graceful shutdown)                       │
│  3. Consumer crashes (heartbeat timeout)                            │
│  4. Consumer stuck in poll (max.poll.interval.ms exceeded)         │
│  5. Topic metadata changes (new partitions added)                  │
│  6. Subscription changes (new topics matched)                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Rebalancing Protocols / Протоколы ребалансировки

#### Eager Rebalancing (Legacy) / Жадная ребалансировка

```
┌─────────────────────────────────────────────────────────────────────┐
│  EAGER REBALANCING (Stop-the-World)                                │
│                                                                      │
│  t0: Rebalance triggered (C3 joins)                                │
│  t1: ALL consumers STOP processing                                 │
│      C1: revoke P0, P1                                             │
│      C2: revoke P2, P3                                             │
│  t2: Reassignment calculated                                        │
│  t3: New assignments distributed                                    │
│      C1: assigned P0                                               │
│      C2: assigned P1, P2                                           │
│      C3: assigned P3                                               │
│  t4: Consumers resume processing                                    │
│                                                                      │
│  Problem: Processing stops for ALL partitions during rebalance     │
│  Duration: Seconds to minutes depending on group size              │
└─────────────────────────────────────────────────────────────────────┘
```

#### Cooperative (Incremental) Rebalancing / Кооперативная ребалансировка

```
┌─────────────────────────────────────────────────────────────────────┐
│  COOPERATIVE REBALANCING (Incremental)                              │
│                                                                      │
│  t0: Rebalance triggered (C3 joins)                                │
│  t1: First rebalance - compute delta                               │
│      C1: keep P0, P1 (no change, continues processing!)           │
│      C2: keep P2, revoke P3                                        │
│      C3: no partitions yet                                         │
│  t2: Second rebalance - reassign revoked                           │
│      C1: keep P0, P1 (still processing!)                           │
│      C2: keep P2 (still processing!)                               │
│      C3: assigned P3                                               │
│  t3: All consumers processing (minimal disruption)                 │
│                                                                      │
│  Benefit: Only affected partitions stop briefly                    │
│  Most partitions continue processing during rebalance!             │
└─────────────────────────────────────────────────────────────────────┘
```

### Enabling Cooperative Rebalancing / Включение кооперативной ребалансировки

```python
from kafka import KafkaConsumer

consumer = KafkaConsumer(
    'orders',
    bootstrap_servers=['localhost:9092'],
    group_id='order-processors',
    # Cooperative rebalancing (Kafka 2.4+)
    partition_assignment_strategy=[
        'org.apache.kafka.clients.consumer.CooperativeStickyAssignor'
    ]
)
```

---

## Assignment Strategies / Стратегии назначения

### Range Assignor / Range-назначение

```
┌─────────────────────────────────────────────────────────────────────┐
│  RANGE ASSIGNOR                                                     │
│                                                                      │
│  Topic: orders (7 partitions), 3 consumers                         │
│  7 / 3 = 2.33 → Some get 3, some get 2                            │
│                                                                      │
│  C1: P0, P1, P2 (first 3)                                         │
│  C2: P3, P4    (next 2)                                            │
│  C3: P5, P6    (last 2)                                            │
│                                                                      │
│  Problem: C1 always gets more partitions! (unfair with many topics)│
└─────────────────────────────────────────────────────────────────────┘
```

### Round-Robin Assignor / Round-Robin назначение

```
┌─────────────────────────────────────────────────────────────────────┐
│  ROUND-ROBIN ASSIGNOR                                               │
│                                                                      │
│  All partitions sorted, distributed one by one                     │
│  + More balanced than Range                                        │
│  - All partitions reassigned on rebalance                          │
└─────────────────────────────────────────────────────────────────────┘
```

### Sticky Assignor / Sticky назначение

```
┌─────────────────────────────────────────────────────────────────────┐
│  STICKY ASSIGNOR                                                    │
│                                                                      │
│  Goal: Minimize partition movements during rebalance               │
│                                                                      │
│  Initial: C1: P0,P1 | C2: P2,P3 | C3: P4,P5                      │
│                                                                      │
│  C3 leaves:                                                         │
│  Round-Robin would: C1: P0,P2,P4 | C2: P1,P3,P5 (4 moved!)      │
│  Sticky keeps:      C1: P0,P1,P4 | C2: P2,P3,P5 (only 2 moved!) │
│                                                                      │
│  + Faster rebalances                                                │
│  + Better for stateful consumers (caches, local state)             │
│  + Less disruption                                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### Cooperative Sticky Assignor (Recommended) / Кооперативный Sticky

```
┌─────────────────────────────────────────────────────────────────────┐
│  COOPERATIVE STICKY ASSIGNOR (Recommended)                          │
│                                                                      │
│  Combines:                                                          │
│  • Sticky: Minimize partition movements                            │
│  • Cooperative: Don't stop all consumers during rebalance          │
│                                                                      │
│  + Minimal partition movements                                      │
│  + Continuous processing during rebalance                          │
│  + Only affected partitions pause briefly                          │
│                                                                      │
│  Configuration:                                                     │
│  partition.assignment.strategy=                                     │
│      org.apache.kafka.clients.consumer.CooperativeStickyAssignor   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Consumer Group Coordinator / Координатор Consumer Group

### Coordinator Role / Роль координатора

```
┌─────────────────────────────────────────────────────────────────────┐
│  GROUP COORDINATOR                                                  │
│                                                                      │
│  Each consumer group has ONE coordinator (broker)                  │
│  Determined by: hash(group.id) % num_partitions(__consumer_offsets)│
│                                                                      │
│  Responsibilities:                                                  │
│  • Track group membership                                          │
│  • Receive heartbeats from consumers                               │
│  • Trigger rebalances when membership changes                      │
│  • Select group leader (first consumer to join)                    │
│  • Store committed offsets in __consumer_offsets                   │
│                                                                      │
│  Leader consumer:                                                   │
│  • Receives member list from coordinator                           │
│  • Computes partition assignment                                   │
│  • Sends assignment back to coordinator                            │
│  • Coordinator distributes to all members                          │
└─────────────────────────────────────────────────────────────────────┘
```

### Heartbeat and Session Management / Heartbeat и управление сессией

```
┌─────────────────────────────────────────────────────────────────────┐
│  CONSUMER HEALTH MONITORING                                         │
│                                                                      │
│  session.timeout.ms = 45000 (default)                              │
│  └─ If no heartbeat within this time → consumer removed            │
│                                                                      │
│  heartbeat.interval.ms = 3000 (default)                            │
│  └─ How often consumer sends heartbeat                             │
│                                                                      │
│  max.poll.interval.ms = 300000 (default, 5 min)                    │
│  └─ Max time between poll() calls → prevents stuck consumers       │
│                                                                      │
│  Tuning recommendations:                                            │
│  • session.timeout.ms >= 3 x heartbeat.interval.ms                 │
│  • Lower session.timeout.ms = faster failure detection             │
│  • Higher = more tolerant to GC pauses, network blips              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Static Group Membership / Статическое членство в группе

### Problem: Rolling Restarts / Проблема: Последовательные перезапуски

```
┌─────────────────────────────────────────────────────────────────────┐
│  ROLLING RESTART WITHOUT STATIC MEMBERSHIP                          │
│                                                                      │
│  Restart C1: C1 leaves → Rebalance! C1 rejoins → Rebalance!       │
│  Restart C2: C2 leaves → Rebalance! C2 rejoins → Rebalance!       │
│  Restart C3: C3 leaves → Rebalance! C3 rejoins → Rebalance!       │
│                                                                      │
│  Total: 6 rebalances for 3 restarts!                               │
│  Each rebalance = processing pause                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### Solution: Static Membership / Решение: Статическое членство

```
┌─────────────────────────────────────────────────────────────────────┐
│  STATIC GROUP MEMBERSHIP (Kafka 2.3+)                               │
│                                                                      │
│  Configuration:                                                     │
│  group.instance.id = "consumer-1"  (unique per consumer)           │
│  session.timeout.ms = 300000       (longer timeout)                │
│                                                                      │
│  Restart C1:                                                        │
│  1. C1 stops → NO rebalance (session timeout not reached)          │
│  2. C1 rejoins with same group.instance.id                         │
│  3. Gets same partitions back immediately!                         │
│                                                                      │
│  + Zero rebalances during rolling restarts                         │
│  + Partitions "reserved" for returning consumer                    │
│  + Faster restarts                                                  │
│                                                                      │
│  Requirements:                                                      │
│  • Each consumer must have unique, stable instance ID              │
│  • Restart must complete within session.timeout.ms                 │
│  • Use hostname or pod name as instance ID                         │
└─────────────────────────────────────────────────────────────────────┘
```

```python
# Static membership configuration
consumer = KafkaConsumer(
    'orders',
    group_id='order-processors',
    group_instance_id=f'consumer-{hostname}',  # Stable ID
    session_timeout_ms=300000,  # 5 minutes to restart
)
```

---

## Best Practices / Лучшие практики

```
┌─────────────────────────────────────────────────────────────────────┐
│  CONSUMER GROUP BEST PRACTICES                                      │
│                                                                      │
│  1. USE COOPERATIVE STICKY ASSIGNOR                                 │
│     → Minimal disruption during rebalances                         │
│                                                                      │
│  2. ENABLE STATIC MEMBERSHIP FOR K8S DEPLOYMENTS                   │
│     group.instance.id=pod-name                                      │
│     → Zero rebalances during rolling updates                       │
│                                                                      │
│  3. TUNE POLL INTERVAL FOR YOUR WORKLOAD                           │
│     max.poll.interval.ms = expected_processing_time x 2            │
│     max.poll.records = batches_you_can_process_in_time             │
│                                                                      │
│  4. HANDLE REBALANCE CALLBACKS                                      │
│     • on_partitions_revoked: commit offsets, cleanup               │
│     • on_partitions_assigned: initialize state                     │
│                                                                      │
│  5. SCALE CONSUMERS = PARTITIONS                                    │
│     consumers > partitions = wasted resources                      │
│     consumers < partitions = underutilized parallelism             │
│                                                                      │
│  6. MONITOR CONSUMER LAG                                            │
│     Alert when lag consistently increases                          │
│     Indicates: consumers can't keep up                             │
└─────────────────────────────────────────────────────────────────────┘
```

## Связано с
- [[Kafka]]
- [[Partitioning]]

## Ресурсы
- [Kafka Consumer Group Protocol](https://kafka.apache.org/documentation/#consumerconfigs)
- [KIP-429: Incremental Cooperative Rebalancing](https://cwiki.apache.org/confluence/display/KAFKA/KIP-429)
- [KIP-345: Static Membership](https://cwiki.apache.org/confluence/display/KAFKA/KIP-345)
- [Confluent: Consumer Group Management](https://docs.confluent.io/platform/current/clients/consumer.html)

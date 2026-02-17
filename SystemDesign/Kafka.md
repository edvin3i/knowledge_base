---
tags:
  - system-design
  - kafka
  - messaging
created: 2026-02-17
---

# Основы Apache Kafka

## Что это
Apache Kafka -- распределённая платформа потоковой передачи событий (distributed event streaming platform), разработанная в LinkedIn (2010). Основная абстракция -- append-only лог с партициями. Используется для event streaming, агрегации логов, сбора метрик и stream processing. [[Redpanda]] -- Kafka-совместимая альтернатива на C++ без JVM.

## What is Apache Kafka? / Что такое Apache Kafka?

**Apache Kafka** is a distributed event streaming platform designed for high-throughput, fault-tolerant, and scalable real-time data pipelines.

**Apache Kafka** -- это распределённая платформа потоковой передачи событий, разработанная для высокопроизводительных, отказоустойчивых и масштабируемых конвейеров данных в реальном времени.

### Origin and Purpose / Происхождение и назначение

- Developed at LinkedIn (2010), open-sourced (2011)
- Named after writer Franz Kafka
- Designed to handle trillions of events per day

**Core use cases / Основные сценарии:**
- Event streaming / Потоковая передача событий
- Log aggregation / Агрегация логов
- Metrics collection / Сбор метрик
- Stream processing / Обработка потоков
- Event sourcing / Event Sourcing

---

## Core Architecture / Архитектура ядра

### Cluster Topology / Топология кластера

```
┌─────────────────────────────────────────────────────────────────────┐
│                        KAFKA CLUSTER                                │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      ZOOKEEPER / KRAFT                       │   │
│  │  (Metadata management, leader election, cluster config)      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│       ┌──────────────────────┼──────────────────────┐              │
│       │                      │                      │              │
│       ▼                      ▼                      ▼              │
│  ┌─────────────┐       ┌─────────────┐       ┌─────────────┐      │
│  │  Broker 1   │       │  Broker 2   │       │  Broker 3   │      │
│  │  ┌───────┐  │       │  ┌───────┐  │       │  ┌───────┐  │      │
│  │  │ P0    │  │       │  │ P0    │  │       │  │ P1    │  │      │
│  │  │(leader│  │       │  │(replica)│ │       │  │(leader│  │      │
│  │  └───────┘  │       │  └───────┘  │       │  └───────┘  │      │
│  │  ┌───────┐  │       │  ┌───────┐  │       │  ┌───────┐  │      │
│  │  │ P1    │  │       │  │ P2    │  │       │  │ P2    │  │      │
│  │  │(replica)│ │       │  │(leader│  │       │  │(replica)│ │      │
│  │  └───────┘  │       │  └───────┘  │       │  └───────┘  │      │
│  └─────────────┘       └─────────────┘       └─────────────┘      │
│                                                                      │
│  Legend: P = Partition                                              │
└─────────────────────────────────────────────────────────────────────┘
```

### Core Components / Основные компоненты

| Component | Role (EN) | Роль (RU) |
|-----------|-----------|-----------|
| **Broker** | Server that stores and serves messages | Сервер, хранящий и раздающий сообщения |
| **Topic** | Logical channel for messages | Логический канал для сообщений |
| **Partition** | Ordered, immutable sequence of records | Упорядоченная, неизменяемая последовательность записей |
| **Producer** | Client that publishes messages | Клиент, публикующий сообщения |
| **Consumer** | Client that reads messages | Клиент, читающий сообщения |
| **[[Consumer-Groups\|Consumer Group]]** | Set of consumers sharing partition load | Группа потребителей, разделяющих нагрузку |
| **ZooKeeper/KRaft** | Cluster coordination (being replaced) | Координация кластера (заменяется) |

---

## The Log: Kafka's Core Abstraction / Лог: основная абстракция Kafka

### Append-Only Log Structure / Структура append-only лога

```
┌─────────────────────────────────────────────────────────────────────┐
│  PARTITION = APPEND-ONLY LOG                                        │
│                                                                      │
│  Topic: "orders", Partition: 0                                      │
│                                                                      │
│  ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐    │
│  │  0  │  1  │  2  │  3  │  4  │  5  │  6  │  7  │  8  │  9  │    │
│  └─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘    │
│    ↑                                                     ↑          │
│  oldest                                              newest         │
│  (may be                                           (write here)    │
│   deleted)                                                          │
│                                                                      │
│  Each slot = Record (message)                                       │
│  Number = Offset (unique within partition)                         │
│                                                                      │
│  Record structure:                                                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ offset | timestamp | key | value | headers                   │   │
│  │ 5      | 170923... | "u1"| {...} | [{"trace": "abc"}]       │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Why Append-Only? / Почему append-only?

1. **Sequential I/O** -- Orders of magnitude faster than random I/O
2. **Immutability** -- No in-place updates, simplifies replication
3. **Predictable performance** -- Constant time writes O(1)
4. **Easy replication** -- Just copy bytes, no complex sync

---

## Replication / Репликация

### ISR: In-Sync Replicas / ISR: Синхронные реплики

```
┌─────────────────────────────────────────────────────────────────────┐
│  REPLICATION MODEL                                                  │
│                                                                      │
│  Topic: orders, Partition: 0, Replication Factor: 3                │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  LEADER (Broker 1)                                          │   │
│  │  ┌─────┬─────┬─────┬─────┬─────┬─────┐                     │   │
│  │  │  0  │  1  │  2  │  3  │  4  │  5  │ ← Writes go here   │   │
│  │  └─────┴─────┴─────┴─────┴─────┴─────┘                     │   │
│  │  High Water Mark (HWM): 5                                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                          │                                          │
│                          │ Fetch requests                           │
│            ┌─────────────┼─────────────┐                           │
│            ▼             ▼             ▼                           │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐               │
│  │ FOLLOWER     │ │ FOLLOWER     │ │ FOLLOWER     │               │
│  │ (Broker 2)   │ │ (Broker 3)   │ │ (Broker 4)   │               │
│  │ [0,1,2,3,4,5]│ │ [0,1,2,3,4,5]│ │ [0,1,2,3]    │ ← Lagging    │
│  │ IN-SYNC      │ │ IN-SYNC      │ │ OUT-OF-SYNC  │               │
│  └──────────────┘ └──────────────┘ └──────────────┘               │
│                                                                      │
│  ISR = {Leader, Broker2, Broker3}                                  │
│  Broker4 will be added back when it catches up                     │
└─────────────────────────────────────────────────────────────────────┘
```

### ISR Dynamics / Динамика ISR

**A replica is IN-SYNC if:**
1. It has fetched all messages up to the leader's log end offset
2. It has sent a fetch request within `replica.lag.time.max.ms`

**Replica falls out of ISR when:**
- Network partition from leader
- Slow disk I/O
- GC pauses
- Process crash/restart

---

## Producer Acknowledgments / Подтверждения Producer

### acks Configuration / Конфигурация acks

```
┌─────────────────────────────────────────────────────────────────────┐
│  PRODUCER ACKS SETTINGS                                             │
│                                                                      │
│  acks=0 (Fire and forget)                                          │
│  • Fastest, lowest latency                                         │
│  • No durability guarantee                                         │
│  • Use for: Metrics, logs (loss acceptable)                        │
│                                                                      │
│  acks=1 (Leader acknowledgment)                                    │
│  • Good balance of speed and durability                            │
│  • Risk: Leader fails before replication                           │
│  • Use for: Most use cases                                         │
│                                                                      │
│  acks=all (All ISR acknowledgment)                                 │
│  • Strongest durability                                             │
│  • Higher latency                                                   │
│  • Use for: Financial data, critical events                        │
└─────────────────────────────────────────────────────────────────────┘
```

### min.insync.replicas / Минимальные синхронные реплики

```
┌─────────────────────────────────────────────────────────────────────┐
│  min.insync.replicas + acks=all                                    │
│                                                                      │
│  Setting: replication.factor=3, min.insync.replicas=2              │
│                                                                      │
│  Scenario 1: All healthy                                           │
│  ISR = {Leader, F1, F2}                                            │
│  Writes succeed (ISR size 3 >= min.insync 2)                       │
│                                                                      │
│  Scenario 2: One follower down                                     │
│  ISR = {Leader, F1}                                                │
│  Writes succeed (ISR size 2 >= min.insync 2)                       │
│                                                                      │
│  Scenario 3: Two followers down                                    │
│  ISR = {Leader}                                                    │
│  Writes REJECTED (ISR size 1 < min.insync 2)                      │
│  → NotEnoughReplicasException                                      │
│                                                                      │
│  Trade-off:                                                         │
│  • Higher min.insync = More durability, less availability          │
│  • Lower min.insync = More availability, less durability           │
│                                                                      │
│  Production recommendation:                                         │
│  replication.factor=3, min.insync.replicas=2, acks=all            │
│  Tolerates 1 broker failure without data loss                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Consumer Offsets / Смещения Consumer

### Offset Management / Управление смещениями

```
┌─────────────────────────────────────────────────────────────────────┐
│  CONSUMER OFFSET TRACKING                                           │
│                                                                      │
│  Partition: orders-0                                                │
│  ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐    │
│  │  0  │  1  │  2  │  3  │  4  │  5  │  6  │  7  │  8  │  9  │    │
│  └─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘    │
│                          ↑              ↑              ↑            │
│                    committed      current read    log end          │
│                     offset          position       offset          │
│                        3                6             9            │
│                                                                      │
│  Consumer lag = Log End Offset - Committed Offset = 9 - 3 = 6     │
└─────────────────────────────────────────────────────────────────────┘
```

### Auto-Commit vs Manual Commit / Авто-коммит vs Ручной коммит

```python
# AUTO-COMMIT (default, risky)
# enable.auto.commit=true, auto.commit.interval.ms=5000
# Risk: Message processed but offset not committed → reprocessing
# Risk: Offset committed but processing failed → data loss

# MANUAL COMMIT (recommended)
from kafka import KafkaConsumer

consumer = KafkaConsumer(
    'orders',
    enable_auto_commit=False,  # Manual control
    group_id='order-processor'
)

for message in consumer:
    try:
        process_message(message)  # Process first
        consumer.commit()         # Then commit
    except Exception as e:
        # Don't commit on failure → will reprocess
        log.error(f"Failed: {e}")
```

### At-Least-Once vs At-Most-Once / Как минимум раз vs Как максимум раз

| Semantic | Implementation | Risk |
|----------|---------------|------|
| **At-most-once** | Commit before processing | Data loss on failure |
| **At-least-once** | Commit after processing | Duplicates on failure |
| **[[Exactly-Once]]** | Transactions (see next section) | Complex, performance cost |

---

## [[Partitioning|Partition Strategy]] / Стратегия партиционирования

### Default Partitioner / Стандартный партиционер

```
┌─────────────────────────────────────────────────────────────────────┐
│  KAFKA PARTITIONER BEHAVIOR                                         │
│                                                                      │
│  IF message has key:                                                │
│     partition = hash(key) % num_partitions                         │
│     → Guarantees: Same key always goes to same partition           │
│     → Enables: Ordering per key                                    │
│                                                                      │
│  IF message has NO key (null):                                      │
│     Sticky Partitioner (Kafka 2.4+):                               │
│     → Batch messages to same partition                             │
│     → Switch partition when batch is full or linger.ms expires     │
│     → Better batching efficiency                                    │
│                                                                      │
│  Example:                                                           │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │ key="user-123" → hash("user-123") % 8 = 3 → Partition 3   │    │
│  │ key="user-456" → hash("user-456") % 8 = 7 → Partition 7   │    │
│  │ key="user-123" → hash("user-123") % 8 = 3 → Partition 3   │    │
│  │ key=null       → Sticky to Partition X until batch full    │    │
│  └────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### Partition Count Considerations / Соображения по количеству партиций

```
┌─────────────────────────────────────────────────────────────────────┐
│  PARTITION COUNT TRADE-OFFS                                         │
│                                                                      │
│  MORE PARTITIONS:                                                   │
│  + Higher parallelism (more consumers can work)                    │
│  + Higher throughput                                                │
│  - More file handles on brokers                                    │
│  - Longer leader election time                                     │
│  - Higher end-to-end latency                                       │
│  - More memory for producer batching                               │
│                                                                      │
│  FEWER PARTITIONS:                                                  │
│  + Lower latency                                                    │
│  + Simpler operations                                               │
│  - Limited parallelism                                              │
│  - Hot partitions possible                                         │
│                                                                      │
│  GUIDELINES:                                                        │
│  • Start with partitions = max(expected_consumers, throughput/10)   │
│  • Can increase later, CANNOT decrease                             │
│  • LinkedIn: 10+ partitions per topic for critical paths           │
│  • Typically: 6-12 for most use cases                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Kafka Internals / Внутренности Kafka

### Log Segment Structure / Структура сегментов лога

```
┌─────────────────────────────────────────────────────────────────────┐
│  LOG SEGMENT FILES                                                  │
│                                                                      │
│  /kafka-logs/orders-0/                                              │
│  ├── 00000000000000000000.log      ← Segment file (messages)       │
│  ├── 00000000000000000000.index    ← Offset index                  │
│  ├── 00000000000000000000.timeindex← Time index                    │
│  ├── 00000000000001000000.log      ← Next segment                  │
│  ├── 00000000000001000000.index                                    │
│  └── 00000000000001000000.timeindex                                │
│                                                                      │
│  File naming: base_offset.extension                                │
│  00000000000001000000.log starts at offset 1,000,000               │
│                                                                      │
│  .index file: sparse index (not every offset)                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ offset 0    → position 0                                     │   │
│  │ offset 500  → position 24576                                │   │
│  │ offset 1000 → position 49152                                │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Fetch Request Flow / Поток Fetch-запроса

```
┌─────────────────────────────────────────────────────────────────────┐
│  CONSUMER FETCH FLOW                                                │
│                                                                      │
│  1. Consumer sends FetchRequest to partition leader                 │
│  2. Broker looks up offset in index                                │
│  3. Broker reads from disk using zero-copy (sendfile):             │
│     sendfile(socket_fd, file_fd, offset, count)                    │
│     → Data goes directly from page cache to NIC                    │
│     → No kernel↔userspace copies                                   │
│  4. Response to consumer with records + high_watermark             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## ZooKeeper to KRaft Migration / Миграция с ZooKeeper на KRaft

### Why KRaft? / Зачем KRaft?

```
┌─────────────────────────────────────────────────────────────────────┐
│  ZOOKEEPER vs KRAFT                                                 │
│                                                                      │
│  ZOOKEEPER (Legacy):                                                │
│  • Separate system to operate                                       │
│  • Metadata split between ZK and brokers                           │
│  • Slower recovery (read from ZK on startup)                       │
│  • Limited scalability (~200k partitions)                          │
│                                                                      │
│  KRAFT (Kafka Raft - New):                                          │
│  • Single system (no external dependency)                          │
│  • Metadata in Kafka itself                                        │
│  • Faster recovery (local metadata log)                            │
│  • Millions of partitions supported                                │
│  • Simpler operations                                               │
│                                                                      │
│  Timeline:                                                          │
│  • Kafka 2.8: KRaft in early access                               │
│  • Kafka 3.3: KRaft production ready                              │
│  • Kafka 4.0: ZooKeeper deprecated                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Performance Tuning / Оптимизация производительности

### Key Producer Configs / Ключевые настройки Producer

| Config | Default | Tuning |
|--------|---------|--------|
| `batch.size` | 16KB | Increase for throughput (64KB-256KB) |
| `linger.ms` | 0 | Increase for batching (5-100ms) |
| `compression.type` | none | Use lz4/zstd for throughput |
| `buffer.memory` | 32MB | Increase for high throughput |
| `acks` | 1 | Set to "all" for durability |

### Key Consumer Configs / Ключевые настройки Consumer

| Config | Default | Tuning |
|--------|---------|--------|
| `fetch.min.bytes` | 1 | Increase for batching |
| `fetch.max.wait.ms` | 500 | Balance with latency needs |
| `max.poll.records` | 500 | Match processing capacity |
| `session.timeout.ms` | 45s | Lower for faster rebalancing |
| `max.poll.interval.ms` | 5min | Match processing time |

---

## [[Redpanda]]: Kafka Alternative / Redpanda: Альтернатива Kafka

### Key Differences / Ключевые отличия

| Aspect | Kafka | [[Redpanda]] |
|--------|-------|----------|
| Language | Java/Scala | C++ |
| JVM | Required | None |
| ZooKeeper | Required (legacy) | None (built-in Raft) |
| Memory model | JVM heap + page cache | Direct memory |
| Tail latency | Higher (GC pauses) | Lower, predictable |
| Resource usage | ~10x more for same load | Efficient |
| Compatibility | N/A | Kafka API compatible |

### Why [[Polyvision]] uses [[Redpanda]] / Почему Polyvision использует Redpanda

1. **No ZooKeeper** -- Simpler operations
2. **Lower latency** -- No JVM GC pauses
3. **Kafka API compatible** -- Use existing Kafka clients
4. **Resource efficient** -- Less memory/CPU for same throughput

## Связано с
- [[Partitioning]]
- [[Consumer-Groups]]
- [[Exactly-Once]]
- [[Redpanda]]

## Ресурсы
- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [Kafka: The Definitive Guide](https://www.confluent.io/resources/kafka-the-definitive-guide/)
- [KIP-500: Replace ZooKeeper with Self-Managed Metadata Quorum](https://cwiki.apache.org/confluence/display/KAFKA/KIP-500)
- [Redpanda Documentation](https://docs.redpanda.com/)
- [LinkedIn Engineering: Kafka](https://engineering.linkedin.com/kafka)

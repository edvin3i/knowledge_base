---
tags:
  - system-design
  - kafka
  - exactly-once
created: 2026-02-17
---

# Exactly-Once Semantics в Kafka

## Что это
Exactly-Once Semantics -- гарантия того, что каждое сообщение обрабатывается ровно один раз: без потерь и без дубликатов. В [[Kafka]] достигается комбинацией идемпотентного Producer (PID + sequence numbers), транзакций (atomic writes + offset commits) и изоляции Read Committed на стороне Consumer. Альтернатива -- идемпотентный Consumer с дедупликацией на уровне приложения (Redis SETNX, DB unique constraints).

## Message Delivery Semantics / Семантики доставки сообщений

### Three Delivery Guarantees / Три гарантии доставки

```
┌─────────────────────────────────────────────────────────────────────┐
│  DELIVERY SEMANTICS                                                 │
│                                                                      │
│  AT-MOST-ONCE (≤1)                                                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Producer sends message, doesn't wait for ACK                 │   │
│  │ OR Consumer commits offset BEFORE processing                 │   │
│  │                                                               │   │
│  │ Result: Message may be LOST, never delivered twice          │   │
│  │ Use case: Metrics, logs (loss acceptable)                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  AT-LEAST-ONCE (≥1)                                                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Producer retries on failure                                  │   │
│  │ Consumer commits offset AFTER processing                     │   │
│  │                                                               │   │
│  │ Result: Message never lost, may be delivered MULTIPLE times │   │
│  │ Use case: Most applications (handle duplicates downstream)  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  EXACTLY-ONCE (=1)                                                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Each message processed exactly once                          │   │
│  │ No loss, no duplicates                                       │   │
│  │                                                               │   │
│  │ Result: Strongest guarantee, highest complexity/cost        │   │
│  │ Use case: Financial transactions, inventory, billing        │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Idempotent Producer / Идемпотентный Producer

### The Duplicate Problem / Проблема дубликатов

```
┌─────────────────────────────────────────────────────────────────────┐
│  DUPLICATE PROBLEM WITHOUT IDEMPOTENCE                              │
│                                                                      │
│  Scenario: Network timeout after broker received message            │
│                                                                      │
│  ┌──────────┐         ┌──────────┐                                 │
│  │ Producer │──msg 1─▶│  Broker  │                                 │
│  │          │         │          │                                 │
│  │          │   ✗ ACK lost (timeout)                               │
│  │          │         │  (msg 1 written)                           │
│  │          │         │                                             │
│  │          │──msg 1─▶│          │  (retry)                        │
│  │          │◀──ACK───│          │                                 │
│  │          │         │  (msg 1 written AGAIN!)                    │
│  └──────────┘         └──────────┘                                 │
│                                                                      │
│  Result: msg 1 appears TWICE in topic                              │
│                                                                      │
│  Real-world impact:                                                 │
│  • Customer charged twice                                           │
│  • Inventory decremented twice                                      │
│  • Duplicate notifications sent                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Idempotent Producer Solution / Решение с идемпотентным Producer

```
┌─────────────────────────────────────────────────────────────────────┐
│  IDEMPOTENT PRODUCER (enable.idempotence=true)                     │
│                                                                      │
│  Producer gets unique ID (PID) and tracks sequence numbers         │
│                                                                      │
│  ┌──────────────┐               ┌──────────────┐                   │
│  │   Producer   │               │    Broker    │                   │
│  │   PID: 123   │               │              │                   │
│  │              │               │              │                   │
│  │ Send:        │               │ Receives:    │                   │
│  │ PID=123      │──────────────▶│ PID=123      │                   │
│  │ Seq=0        │               │ Seq=0        │                   │
│  │ Data="A"     │               │ Data="A"     │                   │
│  │              │               │              │                   │
│  │              │   ✗ ACK lost  │ (Written)    │                   │
│  │              │               │ Expects: 1   │                   │
│  │              │               │              │                   │
│  │ Retry:       │               │ Receives:    │                   │
│  │ PID=123      │──────────────▶│ PID=123      │                   │
│  │ Seq=0        │               │ Seq=0        │◀─ Duplicate!     │
│  │ Data="A"     │               │              │   Seq 0 < 1      │
│  │              │               │              │                   │
│  │              │◀──────────────│ ACK (dedup)  │                   │
│  │              │               │ Not written  │                   │
│  │              │               │ again        │                   │
│  └──────────────┘               └──────────────┘                   │
│                                                                      │
│  Broker tracks: {PID: 123, last_seq: 0}                            │
│  Rejects duplicates (same PID + same/lower seq)                    │
└─────────────────────────────────────────────────────────────────────┘
```

### Enabling Idempotent Producer / Включение идемпотентного Producer

```python
from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    # Enable idempotence
    enable_idempotence=True,
    # These are automatically set when idempotence=True:
    # acks='all',
    # retries=MAX_INT,
    # max_in_flight_requests_per_connection=5
)
```

```java
Properties props = new Properties();
props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);
// Automatically configured:
// props.put(ProducerConfig.ACKS_CONFIG, "all");
// props.put(ProducerConfig.RETRIES_CONFIG, Integer.MAX_VALUE);
```

**Limitations / Ограничения:**
- Only within single producer session
- Producer restart = new PID = no dedup with old messages
- Only prevents duplicates at broker level

---

## Transactions / Транзакции

### Why Transactions? / Зачем транзакции?

```
┌─────────────────────────────────────────────────────────────────────┐
│  STREAM PROCESSING PROBLEM                                          │
│                                                                      │
│  Pattern: Read from topic A, process, write to topic B             │
│                                                                      │
│  ┌─────────┐    ┌─────────────┐    ┌─────────┐                     │
│  │ Topic A │───▶│  Processor  │───▶│ Topic B │                     │
│  └─────────┘    └─────────────┘    └─────────┘                     │
│                        │                                            │
│                        ▼                                            │
│                 Commit offset                                       │
│                                                                      │
│  Failure scenarios:                                                 │
│                                                                      │
│  1. Write to B succeeds, commit fails                              │
│     → On restart: message processed TWICE (duplicate in B)         │
│                                                                      │
│  2. Commit succeeds, write to B fails                              │
│     → On restart: message LOST (offset moved, B doesn't have it)   │
│                                                                      │
│  Need: Atomic "write to B + commit offset"                         │
└─────────────────────────────────────────────────────────────────────┘
```

### Kafka Transactions / Транзакции Kafka

```
┌─────────────────────────────────────────────────────────────────────┐
│  KAFKA TRANSACTIONS                                                 │
│                                                                      │
│  Transaction groups multiple operations atomically:                │
│  • Writes to multiple partitions/topics                            │
│  • Consumer offset commits                                          │
│                                                                      │
│  Either ALL succeed or ALL are rolled back                         │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  BEGIN TRANSACTION                                           │   │
│  │  │                                                           │   │
│  │  ├── Write to orders-0                                       │   │
│  │  ├── Write to orders-1                                       │   │
│  │  ├── Write to payments-0                                     │   │
│  │  ├── Commit offset for input topic                          │   │
│  │  │                                                           │   │
│  │  COMMIT TRANSACTION (or ABORT on failure)                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Key component: transactional.id                                   │
│  • Unique identifier for producer instance                         │
│  • Survives producer restarts                                       │
│  • Broker can recover/abort incomplete transactions               │
└─────────────────────────────────────────────────────────────────────┘
```

### Transaction Workflow / Рабочий процесс транзакции

```
┌─────────────────────────────────────────────────────────────────────┐
│  TRANSACTION LIFECYCLE                                              │
│                                                                      │
│  Producer                    Transaction           Topic            │
│  (TxnId=P1)                  Coordinator           Partitions       │
│     │                             │                    │            │
│     │─── InitTransactions() ────▶│                    │            │
│     │◀── OK (PID assigned) ──────│                    │            │
│     │                             │                    │            │
│     │─── BeginTransaction() ────▶│                    │            │
│     │    (local state only)       │                    │            │
│     │                             │                    │            │
│     │─── Send(topicA, msg1) ─────┼───────────────────▶│            │
│     │    (AddPartition TxnId)     │                    │            │
│     │                             │                    │ [UNCOMMITTED]│
│     │─── Send(topicB, msg2) ─────┼───────────────────▶│            │
│     │                             │                    │ [UNCOMMITTED]│
│     │                             │                    │            │
│     │─── CommitTransaction() ───▶│                    │            │
│     │                             │─── Write markers ─▶│            │
│     │                             │                    │ [COMMITTED] │
│     │◀── Commit OK ──────────────│                    │            │
│     │                             │                    │            │
└─────────────────────────────────────────────────────────────────────┘
```

### Transaction Code Example / Пример кода транзакции

```python
from kafka import KafkaProducer, KafkaConsumer

# Transactional producer setup
producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    transactional_id='my-processor-1',  # Required for transactions
    enable_idempotence=True,  # Automatically enabled
)

# Consumer with isolation level
consumer = KafkaConsumer(
    'input-topic',
    bootstrap_servers=['localhost:9092'],
    group_id='processor-group',
    enable_auto_commit=False,  # Manual commit in transaction
    isolation_level='read_committed',  # Only see committed messages
)

# Initialize transactions (once per producer lifecycle)
producer.init_transactions()

for message in consumer:
    try:
        # Begin transaction
        producer.begin_transaction()

        # Process and produce
        result = process(message.value)
        producer.send('output-topic', value=result)

        # Send offsets as part of transaction
        producer.send_offsets_to_transaction(
            {
                TopicPartition(message.topic, message.partition):
                    OffsetAndMetadata(message.offset + 1, None)
            },
            consumer.group_id
        )

        # Commit transaction (atomic: output + offset)
        producer.commit_transaction()

    except Exception as e:
        # Abort transaction on any failure
        producer.abort_transaction()
        raise
```

---

## Read Committed Isolation / Изоляция Read Committed

### Consumer Isolation Levels / Уровни изоляции Consumer

```
┌─────────────────────────────────────────────────────────────────────┐
│  ISOLATION LEVELS                                                   │
│                                                                      │
│  Partition data:                                                    │
│  ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐                │
│  │ m1  │ m2  │ m3  │ m4  │ m5  │ m6  │ m7  │ m8  │                │
│  │ ✓   │ ✓   │ TXN │ TXN │ TXN │ ✓   │ ✓   │ TXN │                │
│  │     │     │ A   │ A   │ A   │     │     │ B   │                │
│  └─────┴─────┴─────┴─────┴─────┴─────┴─────┴─────┘                │
│                           │                   │                     │
│                     TXN A: ABORTED      TXN B: PENDING             │
│                                                                      │
│  READ_UNCOMMITTED (default):                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Sees: m1, m2, m3, m4, m5, m6, m7, m8                        │   │
│  │ (ALL messages, including uncommitted and aborted)           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  READ_COMMITTED:                                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Sees: m1, m2, m6, m7                                        │   │
│  │ (Only committed, non-transactional messages)                │   │
│  │ Skips: m3,m4,m5 (aborted), m8 (pending)                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Enabling Read Committed / Включение Read Committed

```python
consumer = KafkaConsumer(
    'topic',
    bootstrap_servers=['localhost:9092'],
    isolation_level='read_committed'  # Only see committed messages
)
```

---

## Exactly-Once Stream Processing / Exactly-Once обработка потоков

### End-to-End Exactly-Once / Сквозной Exactly-Once

```
┌─────────────────────────────────────────────────────────────────────┐
│  EXACTLY-ONCE STREAM PROCESSING                                     │
│                                                                      │
│  Requirements for end-to-end exactly-once:                         │
│                                                                      │
│  1. IDEMPOTENT PRODUCER                                             │
│     enable.idempotence=true                                         │
│     → No duplicates from producer retries                          │
│                                                                      │
│  2. TRANSACTIONAL PRODUCER                                          │
│     transactional.id=unique-id                                      │
│     → Atomic writes + offset commits                               │
│                                                                      │
│  3. READ_COMMITTED CONSUMER                                         │
│     isolation.level=read_committed                                  │
│     → Only see committed messages                                  │
│                                                                      │
│  4. TRANSACTION-AWARE OFFSET MANAGEMENT                            │
│     send_offsets_to_transaction()                                   │
│     → Offsets committed atomically with output                     │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                                                                │  │
│  │  Input ──▶ [Consumer] ──▶ [Process] ──▶ [Producer] ──▶ Output │  │
│  │  Topic     read_committed              transactional    Topic │  │
│  │                │                            │                  │  │
│  │                └──── ATOMIC TRANSACTION ────┘                  │  │
│  │                                                                │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Kafka Streams Exactly-Once / Exactly-Once в Kafka Streams

```java
// Kafka Streams configuration
Properties props = new Properties();
props.put(StreamsConfig.PROCESSING_GUARANTEE_CONFIG,
          StreamsConfig.EXACTLY_ONCE_V2);  // Kafka 2.5+

// Or for older versions:
// props.put(StreamsConfig.PROCESSING_GUARANTEE_CONFIG,
//           StreamsConfig.EXACTLY_ONCE);

KafkaStreams streams = new KafkaStreams(builder.build(), props);
streams.start();
```

---

## Performance Considerations / Соображения производительности

### Transaction Overhead / Накладные расходы транзакций

```
┌─────────────────────────────────────────────────────────────────────┐
│  TRANSACTION PERFORMANCE IMPACT                                     │
│                                                                      │
│  Additional network round-trips:                                    │
│  • InitTransactions: 1 RTT (once per producer)                     │
│  • BeginTransaction: Local only                                    │
│  • AddPartitionsToTxn: 1 RTT per new partition                     │
│  • CommitTransaction: 2 RTT (prepare + commit markers)             │
│                                                                      │
│  Typical overhead:                                                  │
│  • Latency: +10-50ms per transaction                               │
│  • Throughput: ~3-20% reduction                                    │
│                                                                      │
│  Optimization strategies:                                           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 1. BATCH MESSAGES IN TRANSACTIONS                            │   │
│  │    Don't commit after every message                          │   │
│  │    Batch 100-1000 messages per transaction                   │   │
│  │                                                               │   │
│  │ 2. MINIMIZE PARTITIONS PER TRANSACTION                       │   │
│  │    Each new partition = extra RTT                            │   │
│  │                                                               │   │
│  │ 3. TUNE transaction.timeout.ms                               │   │
│  │    Default: 60s, lower for faster abort detection            │   │
│  │                                                               │   │
│  │ 4. USE EXACTLY_ONCE_V2 (Kafka 2.5+)                          │   │
│  │    Fewer partitions in __transaction_state                   │   │
│  │    Better scalability                                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### When to Use Transactions / Когда использовать транзакции

| Use Case | Need Transactions? | Alternative |
|----------|-------------------|-------------|
| Financial transfers | Yes | N/A |
| Stream processing (read-process-write) | Yes | N/A |
| Simple event publishing | No | Idempotent producer |
| Metrics/logs | No | At-least-once + dedup |
| Order updates | Maybe | Idempotent consumer |

---

## Alternative: Idempotent Consumer / Альтернатива: Идемпотентный Consumer

### Application-Level Deduplication / Дедупликация на уровне приложения

```python
import redis
from kafka import KafkaConsumer

consumer = KafkaConsumer('events', group_id='processor')
redis_client = redis.Redis()

def process_with_deduplication(message):
    # Extract unique identifier
    event_id = message.value['event_id']
    dedup_key = f"processed:{event_id}"

    # Check if already processed
    if redis_client.setnx(dedup_key, "1"):
        # First time seeing this event
        redis_client.expire(dedup_key, 86400 * 7)  # 7 day TTL

        # Process the event
        result = process_event(message.value)

        # Store result (idempotently)
        save_result(event_id, result)
    else:
        # Duplicate, skip processing
        logger.info(f"Skipping duplicate: {event_id}")

for message in consumer:
    process_with_deduplication(message)
    consumer.commit()
```

### Database-Level Deduplication / Дедупликация на уровне БД

```sql
-- Use unique constraint to prevent duplicates
CREATE TABLE processed_events (
    event_id VARCHAR(255) PRIMARY KEY,
    result JSONB,
    processed_at TIMESTAMP DEFAULT NOW()
);

-- Insert with conflict handling
INSERT INTO processed_events (event_id, result)
VALUES ($1, $2)
ON CONFLICT (event_id) DO NOTHING;  -- Idempotent!
```

---

## Summary / Итоги

```
┌─────────────────────────────────────────────────────────────────────┐
│  EXACTLY-ONCE SEMANTICS SUMMARY                                     │
│                                                                      │
│  IDEMPOTENT PRODUCER:                                               │
│  • Prevents duplicates from retries                                │
│  • enable.idempotence=true                                         │
│  • No application changes needed                                    │
│  • Limited to single producer session                              │
│                                                                      │
│  TRANSACTIONS:                                                      │
│  • Atomic multi-partition writes                                    │
│  • Atomic offset commits                                            │
│  • transactional.id required                                        │
│  • Performance overhead                                             │
│                                                                      │
│  READ_COMMITTED:                                                    │
│  • Consumer only sees committed messages                           │
│  • Required for transactional consumers                            │
│                                                                      │
│  IDEMPOTENT CONSUMER (Alternative):                                 │
│  • Application-level deduplication                                  │
│  • Redis SETNX or DB unique constraints                            │
│  • Works without Kafka transactions                                │
│  • More flexible, works with external systems                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Связано с
- [[Kafka]]
- [[Idempotency]]

## Ресурсы
- [Kafka Transactions](https://kafka.apache.org/documentation/#semantics)
- [KIP-98: Exactly Once Delivery and Transactional Messaging](https://cwiki.apache.org/confluence/display/KAFKA/KIP-98)
- [KIP-447: Exactly-Once Support for Kafka Streams](https://cwiki.apache.org/confluence/display/KAFKA/KIP-447)
- [Confluent: Exactly-Once Semantics](https://www.confluent.io/blog/exactly-once-semantics-are-possible-heres-how-apache-kafka-does-it/)

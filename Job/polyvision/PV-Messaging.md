---
tags:
  - polyvision
  - system-design
  - messaging
  - redpanda
created: 2026-02-17
---

# Решение по брокеру сообщений для [[Polyvision]]

## Что это
Архитектурное решение (ADR) по выбору [[Redpanda]] в качестве брокера сообщений для [[Polyvision]]. Redpanda -- Kafka-совместимый брокер на C++ без ZooKeeper, с низкой латентностью и минимальными операционными затратами. Используется для event streaming (domain events), координации оркестратора (consumer groups), декаплинга сервисов и аудита событий. Идемпотентность обеспечивается паттерном Redis SETNX на уровне Consumer.

## Context / Контекст

[[Polyvision]] needs a message broker for:

1. **Event streaming** -- Publishing domain events (job commands, match events)
2. **Orchestrator coordination** -- Distributing work across replicas
3. **Service decoupling** -- Loose coupling between microservices
4. **Audit trail** -- Retaining events for debugging and replay

### Requirements / Требования

| Requirement | Priority | Notes |
|-------------|----------|-------|
| [[Kafka]] API compatibility | High | Ecosystem, tooling, libraries |
| Operational simplicity | High | Small team, limited ops bandwidth |
| Low latency | Medium | Real-time job status updates |
| Durability | High | Cannot lose job commands |
| Horizontal scalability | Medium | Expected growth, but not massive |
| Resource efficiency | Medium | Cost-conscious deployment |

---

## Alternatives Considered / Рассмотренные альтернативы

### 1. Apache Kafka

```
┌─────────────────────────────────────────────────────────────────────┐
│  APACHE KAFKA                                                       │
│                                                                      │
│  Pros:                                                              │
│  ✓ Industry standard                                                │
│  ✓ Massive community and ecosystem                                 │
│  ✓ Proven at extreme scale (LinkedIn, Netflix)                     │
│  ✓ Rich tooling (Kafka Connect, ksqlDB, Schema Registry)          │
│  ✓ Excellent documentation                                         │
│                                                                      │
│  Cons:                                                              │
│  ✗ Requires ZooKeeper (legacy) or KRaft (newer)                   │
│  ✗ JVM-based: GC pauses affect tail latency                       │
│  ✗ High resource consumption (~10x vs Redpanda for same load)     │
│  ✗ Complex operations: JVM tuning, ZK management                  │
│  ✗ Minimum cluster: 3 brokers + 3 ZK = 6 nodes                    │
│                                                                      │
│  Verdict: Overkill for Polyvision's scale                          │
└─────────────────────────────────────────────────────────────────────┘
```

### 2. Redpanda

```
┌─────────────────────────────────────────────────────────────────────┐
│  REDPANDA                                                           │
│                                                                      │
│  Pros:                                                              │
│  ✓ Kafka API compatible (drop-in replacement)                      │
│  ✓ No ZooKeeper (built-in Raft consensus)                         │
│  ✓ C++ implementation: No JVM, no GC pauses                       │
│  ✓ Lower latency, predictable tail latency                        │
│  ✓ 10x more resource efficient than Kafka                         │
│  ✓ Single binary, simple deployment                               │
│  ✓ Built-in Schema Registry (compatible API)                      │
│  ✓ Minimum cluster: 3 nodes                                        │
│                                                                      │
│  Cons:                                                              │
│  ✗ Smaller community than Kafka                                    │
│  ✗ Some advanced Kafka features not yet supported                 │
│  ✗ Less battle-tested at extreme scale                            │
│  ✗ Vendor concentration risk                                       │
│                                                                      │
│  Verdict: Best fit for Polyvision                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### 3. RabbitMQ

```
┌─────────────────────────────────────────────────────────────────────┐
│  RABBITMQ                                                           │
│                                                                      │
│  Pros:                                                              │
│  ✓ Mature, widely adopted                                          │
│  ✓ Multiple protocols (AMQP, MQTT, STOMP)                         │
│  ✓ Flexible routing (exchanges, queues)                           │
│  ✓ Built-in management UI                                          │
│  ✓ Good for task queues                                            │
│                                                                      │
│  Cons:                                                              │
│  ✗ Not designed for event streaming                               │
│  ✗ Messages deleted after consumption                              │
│  ✗ Different API (not Kafka-compatible)                           │
│  ✗ Limited scalability for streaming workloads                    │
│  ✗ Consumer groups work differently                               │
│                                                                      │
│  Verdict: Wrong paradigm for event streaming                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 4. AWS SQS + SNS / Google Cloud Pub/Sub

```
┌─────────────────────────────────────────────────────────────────────┐
│  MANAGED CLOUD SERVICES                                             │
│                                                                      │
│  Pros:                                                              │
│  ✓ Zero operations (fully managed)                                 │
│  ✓ Built-in scaling and durability                                 │
│  ✓ Pay per use                                                      │
│                                                                      │
│  Cons:                                                              │
│  ✗ Vendor lock-in                                                  │
│  ✗ Not Kafka-compatible                                            │
│  ✗ Higher latency than self-hosted                                │
│  ✗ Different semantics (no true consumer groups)                  │
│  ✗ Harder to develop locally                                       │
│                                                                      │
│  Verdict: Lock-in and API incompatibility                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Decision: Redpanda / Решение: Redpanda

### Rationale / Обоснование

```
┌─────────────────────────────────────────────────────────────────────┐
│  WHY REDPANDA FOR POLYVISION                                        │
│                                                                      │
│  1. KAFKA API COMPATIBILITY                                         │
│     • Use standard Kafka clients (kafka-python, confluent-kafka)   │
│     • Rich ecosystem of tools and libraries                        │
│     • Easy migration path if needed                                │
│                                                                      │
│  2. OPERATIONAL SIMPLICITY                                          │
│     • No ZooKeeper to manage                                        │
│     • Single binary deployment                                      │
│     • Built-in Raft consensus                                       │
│     • Simple configuration                                          │
│                                                                      │
│  3. RESOURCE EFFICIENCY                                             │
│     • Runs on smaller instances                                     │
│     • Lower memory footprint                                        │
│     • Reduces infrastructure costs                                  │
│                                                                      │
│  4. PREDICTABLE LATENCY                                             │
│     • No JVM garbage collection pauses                             │
│     • Important for real-time job status updates                   │
│                                                                      │
│  5. CONSUMER GROUPS FOR ORCHESTRATOR HA                            │
│     • Same mechanism as Kafka                                       │
│     • Partition-based work distribution                            │
│     • Automatic rebalancing                                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Topic Design / Дизайн топиков

### Topic Structure / Структура топиков

```
┌─────────────────────────────────────────────────────────────────────┐
│  POLYVISION KAFKA TOPICS                                            │
│                                                                      │
│  polyvision.jobs.commands (8 partitions)                           │
│  ├─ Purpose: Job creation, cancellation commands                   │
│  ├─ Key: {organization_id}:{match_id}                              │
│  ├─ Retention: 7 days                                               │
│  └─ Consumers: Orchestrator (processing-orchestrator group)        │
│                                                                      │
│  polyvision.jobs.events (8 partitions)                             │
│  ├─ Purpose: Job lifecycle events (started, progress, completed)   │
│  ├─ Key: {job_id}                                                  │
│  ├─ Retention: 30 days                                              │
│  └─ Consumers: Multiple (analytics, notifications, etc.)           │
│                                                                      │
│  polyvision.matches.events (8 partitions)                          │
│  ├─ Purpose: Match lifecycle (uploaded, processed, ready)          │
│  ├─ Key: {organization_id}:{match_id}                              │
│  ├─ Retention: 30 days                                              │
│  └─ Consumers: Catalog service, delivery service                   │
│                                                                      │
│  polyvision.analytics.events (4 partitions)                        │
│  ├─ Purpose: Analytics computation events                          │
│  ├─ Key: {match_id}                                                │
│  ├─ Retention: 7 days                                               │
│  └─ Consumers: Analytics aggregator                                │
│                                                                      │
│  polyvision.plugins.events (4 partitions)                          │
│  ├─ Purpose: Plugin health, registration events                    │
│  ├─ Key: {plugin_id}                                               │
│  ├─ Retention: 7 days                                               │
│  └─ Consumers: Plugin manager                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Partition Key Strategy / Стратегия partition key

```
┌─────────────────────────────────────────────────────────────────────┐
│  PARTITION KEY DESIGN                                               │
│                                                                      │
│  Key format: {organization_id}:{match_id}                          │
│                                                                      │
│  Benefits:                                                          │
│  1. ORDERING GUARANTEE                                              │
│     All events for a match go to same partition                    │
│     → Processed in order (upload → stitch → detect → ...)         │
│                                                                      │
│  2. TENANT ISOLATION                                                │
│     Organization ID in key enables future partition-by-tenant      │
│     → Dedicated partitions for large customers if needed           │
│                                                                      │
│  3. LOAD DISTRIBUTION                                               │
│     Different matches spread across partitions                     │
│     → Parallel processing of multiple matches                      │
│                                                                      │
│  Example:                                                           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ "org-1:match-100" → hash → Partition 3                      │   │
│  │ "org-1:match-101" → hash → Partition 7 (different match)    │   │
│  │ "org-2:match-200" → hash → Partition 1 (different org)      │   │
│  │                                                               │   │
│  │ All events for org-1:match-100 → Partition 3 (ordered)      │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Orchestrator [[Consumer-Groups|Consumer Group]] / Consumer Group оркестратора

### High Availability Design / Дизайн высокой доступности

```
┌─────────────────────────────────────────────────────────────────────┐
│  ORCHESTRATOR HA WITH REDPANDA CONSUMER GROUPS                      │
│                                                                      │
│  Consumer Group: processing-orchestrator                           │
│  Topic: polyvision.jobs.commands (8 partitions)                    │
│                                                                      │
│  Normal operation (2 replicas):                                    │
│  ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐                │
│  │ P0  │ P1  │ P2  │ P3  │ P4  │ P5  │ P6  │ P7  │                │
│  └──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴──┬──┘                │
│     └──┬──┴──┬──┘     └──┬──┴──┬──┘                                │
│        │     │           │     │                                    │
│        ▼     ▼           ▼     ▼                                    │
│  ┌─────────────────┐  ┌─────────────────┐                          │
│  │  Orchestrator   │  │  Orchestrator   │                          │
│  │   Replica 1     │  │   Replica 2     │                          │
│  │   (P0-P3)       │  │   (P4-P7)       │                          │
│  └─────────────────┘  └─────────────────┘                          │
│                                                                      │
│  Failover (Replica 1 dies):                                        │
│  ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐                │
│  │ P0  │ P1  │ P2  │ P3  │ P4  │ P5  │ P6  │ P7  │                │
│  └──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴──┬──┴──┬──┘                │
│     └──────────────────────────────────────────┘                    │
│                          │                                          │
│                          ▼                                          │
│                 ┌─────────────────┐                                │
│                 │  Orchestrator   │                                │
│                 │   Replica 2     │                                │
│                 │   (P0-P7)       │ ← Takes over ALL partitions   │
│                 └─────────────────┘                                │
│                                                                      │
│  Rebalancing Time: ~10 seconds (session.timeout.ms)                │
└─────────────────────────────────────────────────────────────────────┘
```

### Consumer Configuration / Конфигурация consumer

```python
from kafka import KafkaConsumer
import socket

consumer = KafkaConsumer(
    'polyvision.jobs.commands',
    bootstrap_servers=['redpanda:9092'],
    group_id='processing-orchestrator',

    # Cooperative rebalancing (minimal disruption)
    partition_assignment_strategy=[
        'org.apache.kafka.clients.consumer.CooperativeStickyAssignor'
    ],

    # Static membership (zero rebalances on rolling restart)
    group_instance_id=f'orchestrator-{socket.gethostname()}',
    session_timeout_ms=30000,  # 30 seconds for restart

    # Manual offset management (for idempotency)
    enable_auto_commit=False,

    # Read committed only (future-proofing for transactions)
    isolation_level='read_committed',

    # Batch processing
    max_poll_records=100,
    fetch_max_wait_ms=500,
)
```

---

## Idempotency Pattern / Паттерн идемпотентности

### Redis-Based Deduplication / Дедупликация через Redis

```python
import redis
from kafka import KafkaConsumer

redis_client = redis.Redis(host='redis-celery', port=6379)

async def handle_job_command(message):
    """
    Process job command with idempotency guarantee.

    Key insight: During rebalancing, a message might be processed by
    old consumer AND new consumer. Redis SETNX ensures only one succeeds.
    """
    payload = json.loads(message.value)
    job_id = payload['job_id']
    command_type = payload['command_type']

    # Idempotency key includes command type
    idempotency_key = f"job:processed:{job_id}:{command_type}"

    # SETNX returns True only for first caller
    if redis_client.setnx(idempotency_key, "1"):
        # Set expiry for cleanup (7 days)
        redis_client.expire(idempotency_key, 86400 * 7)

        # Process the command
        if command_type == 'CREATE':
            await create_processing_tasks(job_id, payload)
        elif command_type == 'CANCEL':
            await cancel_processing_tasks(job_id)

        logger.info(f"Processed: {job_id} ({command_type})")
    else:
        # Duplicate - skip silently
        logger.debug(f"Duplicate skipped: {job_id} ({command_type})")

    # Commit offset (after idempotent processing)
    consumer.commit()
```

---

## Configuration / Конфигурация

### Redpanda Cluster Settings / Настройки кластера Redpanda

```yaml
# docker-compose.yml
services:
  redpanda:
    image: docker.redpanda.com/redpandadata/redpanda:v23.3.5
    command:
      - redpanda start
      - --smp 2
      - --memory 2G
      - --reserve-memory 0M
      - --overprovisioned
      - --kafka-addr PLAINTEXT://0.0.0.0:9092
      - --advertise-kafka-addr PLAINTEXT://redpanda:9092
      - --pandaproxy-addr 0.0.0.0:8082
      - --advertise-pandaproxy-addr redpanda:8082
    ports:
      - "9092:9092"
      - "8082:8082"  # HTTP Proxy (REST API)
      - "9644:9644"  # Admin API
    volumes:
      - redpanda_data:/var/lib/redpanda/data
```

### Topic Creation / Создание топиков

```bash
# Create topics with rpk (Redpanda CLI)
rpk topic create polyvision.jobs.commands \
    --partitions 8 \
    --replicas 3 \
    --config retention.ms=604800000  # 7 days

rpk topic create polyvision.jobs.events \
    --partitions 8 \
    --replicas 3 \
    --config retention.ms=2592000000  # 30 days

rpk topic create polyvision.matches.events \
    --partitions 8 \
    --replicas 3 \
    --config retention.ms=2592000000  # 30 days
```

---

## Trade-offs Accepted / Принятые компромиссы

```
┌─────────────────────────────────────────────────────────────────────┐
│  TRADE-OFFS                                                         │
│                                                                      │
│  1. SMALLER COMMUNITY THAN KAFKA                                    │
│     Risk: Fewer resources, slower issue resolution                 │
│     Mitigation: API compatibility means Kafka docs mostly apply    │
│                                                                      │
│  2. VENDOR CONCENTRATION                                            │
│     Risk: Single company behind Redpanda                           │
│     Mitigation: Kafka-compatible API = easy migration if needed    │
│                                                                      │
│  3. LESS BATTLE-TESTED AT EXTREME SCALE                            │
│     Risk: Unknown issues at very high throughput                   │
│     Mitigation: Polyvision's scale is well within Redpanda's       │
│     proven capabilities                                             │
│                                                                      │
│  4. NO KAFKA TRANSACTIONS (simplified)                              │
│     Risk: Need application-level exactly-once                      │
│     Mitigation: Idempotent consumer pattern with Redis             │
│     (actually simpler and more flexible)                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Interview Questions / Вопросы для интервью

### Q: Why Redpanda over Kafka?
**Почему Redpanda вместо Kafka?**

**Answer:** [[Redpanda]] offers [[Kafka]] API compatibility with significantly lower operational complexity. For [[Polyvision]]'s scale:
- No ZooKeeper to manage
- Lower resource consumption
- Predictable latency (no JVM GC)
- Simpler deployment

Kafka's extreme scalability is overkill for our use case.

### Q: How does the partition key strategy support ordering?
**Как стратегия partition key поддерживает упорядочивание?**

**Answer:** Key format `{org_id}:{match_id}` ensures:
1. All events for a match hash to the same partition
2. Single partition = single consumer = ordered processing
3. Different matches distribute across partitions for parallelism

### Q: How do you handle duplicates during rebalancing?
**Как обрабатываются дубликаты во время ребалансировки?**

**Answer:** Redis SETNX pattern:
1. Generate idempotency key from job_id + command_type
2. SETNX returns true only for first caller
3. Set TTL for automatic cleanup
4. Skip processing if SETNX returns false

## Связано с
- [[Polyvision]]
- [[Kafka]]
- [[Redpanda]]

## Ресурсы
- [Redpanda Documentation](https://docs.redpanda.com/)
- [Redpanda vs Kafka Comparison](https://redpanda.com/comparison/redpanda-vs-kafka)
- [Kafka Consumer Groups](https://kafka.apache.org/documentation/#consumerconfigs)
- [Cooperative Sticky Assignor](https://www.redpanda.com/guides/kafka-performance-kafka-rebalancing)

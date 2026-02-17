---
tags:
  - system-design
  - kafka
  - partitioning
created: 2026-02-17
---

# Стратегии партиционирования в Kafka

## Что это
Партиционирование -- основа масштабируемости [[Kafka]]. Стратегия выбора partition key определяет параллелизм обработки, гарантии порядка и распределение нагрузки. Включает встроенные (default/round-robin/sticky) и кастомные партиционеры.

## Why Partitioning Matters / Почему партиционирование важно

Partitioning is the foundation of [[Kafka]]'s scalability. Understanding partition strategies is crucial for:

Партиционирование -- основа масштабируемости [[Kafka]]. Понимание стратегий партиционирования критично для:

- **Parallelism** -- More partitions = more consumers working in parallel
- **Ordering** -- Messages with same key go to same partition -> ordered processing
- **Load distribution** -- Even distribution prevents hot partitions
- **Scalability** -- Can increase partitions (but not decrease!)

---

## Built-in Partitioners / Встроенные партиционеры

### 1. Default Partitioner (Key-Based Hashing) / Стандартный партиционер

```
┌─────────────────────────────────────────────────────────────────────┐
│  DEFAULT PARTITIONER (murmur2 hash)                                │
│                                                                      │
│  WHEN KEY IS PRESENT:                                               │
│  partition = hash(key) % num_partitions                            │
│                                                                      │
│  Examples (8 partitions):                                           │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │ key="user-001" → murmur2("user-001") % 8 = 3               │    │
│  │ key="user-002" → murmur2("user-002") % 8 = 7               │    │
│  │ key="user-001" → murmur2("user-001") % 8 = 3  (same!)      │    │
│  │ key="org:123"  → murmur2("org:123")  % 8 = 1               │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  Guarantees: All messages with same key → same partition            │
│  Use case: Order processing (all events for order together)        │
│  Warning: Adding partitions changes key→partition mapping!          │
└─────────────────────────────────────────────────────────────────────┘
```

### 2. Round-Robin Partitioner / Round-Robin партиционер

```
┌─────────────────────────────────────────────────────────────────────┐
│  ROUND-ROBIN PARTITIONER                                            │
│                                                                      │
│  Messages distributed cyclically across partitions                  │
│                                                                      │
│  Message 1 → Partition 0                                            │
│  Message 2 → Partition 1                                            │
│  Message 3 → Partition 2                                            │
│  Message 4 → Partition 0 (cycle)                                    │
│                                                                      │
│  + Perfect load balance                                             │
│  + Use case: Independent events, no ordering needed                │
│  - No ordering guarantees                                          │
│  - Poor batching (messages spread across partitions)               │
└─────────────────────────────────────────────────────────────────────┘
```

### 3. Sticky Partitioner ([[Kafka]] 2.4+) / Sticky партиционер

```
┌─────────────────────────────────────────────────────────────────────┐
│  STICKY PARTITIONER (Default for null keys since 2.4)              │
│                                                                      │
│  Problem with Round-Robin:                                          │
│  Batch 1: [msg1→P0] [msg2→P1] [msg3→P2]                           │
│  Result: 3 small network requests                                   │
│                                                                      │
│  Sticky Partitioner solution:                                       │
│  Pick random partition, stick to it until:                          │
│  • batch.size reached, OR                                           │
│  • linger.ms expires                                                │
│                                                                      │
│  Batch 1: [msg1, msg2, msg3] → P0 (1 request)                     │
│  Batch 2: [msg4, msg5, msg6] → P2 (switch to random)              │
│                                                                      │
│  + Better batching efficiency                                       │
│  + Lower latency (fewer requests)                                  │
│  + Eventually uniform distribution                                 │
│  - Short-term partition imbalance                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Custom Partitioner / Кастомный партиционер

### When to Use Custom Partitioner / Когда использовать кастомный

1. **Composite keys** -- Need to partition on part of the key
2. **Priority routing** -- High-priority messages to specific partitions
3. **Geo-based routing** -- Route by region
4. **Load-aware routing** -- Avoid hot partitions dynamically

### Python Example / Пример на Python

```python
from kafka import KafkaProducer
import hashlib

class TenantAwarePartitioner:
    """
    Partition key format: {tenant_id}:{entity_id}
    Partition by tenant_id only for tenant isolation
    """

    def __call__(self, key, all_partitions, available_partitions):
        if key is None:
            # Random partition for null keys
            return random.choice(available_partitions)

        # Extract tenant_id from key
        key_str = key.decode('utf-8') if isinstance(key, bytes) else key
        tenant_id = key_str.split(':')[0]

        # Hash only tenant_id
        hash_value = int(hashlib.md5(tenant_id.encode()).hexdigest(), 16)
        partition = hash_value % len(all_partitions)

        # Return partition if available, else random available
        if partition in available_partitions:
            return partition
        return random.choice(available_partitions)


# Usage
producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    key_serializer=str.encode,
    value_serializer=lambda v: json.dumps(v).encode(),
    partitioner=TenantAwarePartitioner()
)

# All events for org-123 go to same partition
producer.send('events', key='org-123:match-456', value={'type': 'created'})
producer.send('events', key='org-123:match-789', value={'type': 'created'})
# Both go to same partition (partitioned by org-123)
```

### Java Example / Пример на Java

```java
public class PriorityPartitioner implements Partitioner {

    private static final int HIGH_PRIORITY_PARTITIONS = 2;

    @Override
    public int partition(String topic, Object key, byte[] keyBytes,
                        Object value, byte[] valueBytes, Cluster cluster) {

        List<PartitionInfo> partitions = cluster.partitionsForTopic(topic);
        int numPartitions = partitions.size();

        // Parse priority from key: "HIGH:order-123" or "LOW:order-456"
        String keyStr = (String) key;
        boolean isHighPriority = keyStr != null && keyStr.startsWith("HIGH:");

        if (isHighPriority) {
            // Route to first N partitions (dedicated workers)
            String orderId = keyStr.substring(5);
            return Math.abs(orderId.hashCode()) % HIGH_PRIORITY_PARTITIONS;
        } else {
            // Route to remaining partitions
            String orderId = keyStr != null ? keyStr.substring(4) : "";
            int partition = Math.abs(orderId.hashCode()) % (numPartitions - HIGH_PRIORITY_PARTITIONS);
            return partition + HIGH_PRIORITY_PARTITIONS;
        }
    }

    @Override
    public void close() {}

    @Override
    public void configure(Map<String, ?> configs) {}
}
```

---

## Partition Key Design Patterns / Паттерны дизайна partition key

### Pattern 1: Entity-Based Key / Ключ на основе сущности

```
┌─────────────────────────────────────────────────────────────────────┐
│  ENTITY-BASED KEY                                                   │
│                                                                      │
│  Use case: Order processing, user events                           │
│  Key format: entity_id                                              │
│                                                                      │
│  Examples:                                                          │
│  • key="order-12345"     → All order events together               │
│  • key="user-98765"      → All user events together                │
│                                                                      │
│  + Guaranteed ordering per entity                                  │
│  + Simple to implement                                             │
│  - Hot partitions if some entities have many events                │
│  - Key cardinality affects distribution                            │
└─────────────────────────────────────────────────────────────────────┘
```

### Pattern 2: Composite Key / Составной ключ

```
┌─────────────────────────────────────────────────────────────────────┐
│  COMPOSITE KEY                                                      │
│                                                                      │
│  Use case: Multi-tenant systems, hierarchical data                 │
│  Key format: {tenant}:{entity}                                      │
│                                                                      │
│  [[Polyvision]] example:                                            │
│  key = f"{organization_id}:{match_id}"                             │
│                                                                      │
│  "org-1:match-100" → All events for match-100 of org-1             │
│  "org-1:match-101" → Different partition (different match)         │
│  "org-2:match-100" → Different partition (different org)           │
│                                                                      │
│  + Tenant isolation                                                 │
│  + Match-level ordering                                            │
│  + Good distribution across partitions                             │
│                                                                      │
│  Variant: Partition by tenant only (custom partitioner)            │
│  → All tenant data on same partition for locality                  │
└─────────────────────────────────────────────────────────────────────┘
```

### Pattern 3: Time-Based Key / Ключ на основе времени

```
┌─────────────────────────────────────────────────────────────────────┐
│  TIME-BASED KEY                                                     │
│                                                                      │
│  Use case: Time-series data, logs                                  │
│  Key format: {entity}:{time_bucket}                                 │
│                                                                      │
│  Examples:                                                          │
│  • key="sensor-1:2024-01-15"  → All readings for day               │
│  • key="service-a:2024-01-15-14" → All logs for hour               │
│                                                                      │
│  + Even distribution over time                                     │
│  + Easy time-based queries                                         │
│  - Hot partition at current time bucket                            │
│  - Need to handle bucket boundaries                                │
└─────────────────────────────────────────────────────────────────────┘
```

### Pattern 4: Random with Deduplication / Случайный с дедупликацией

```
┌─────────────────────────────────────────────────────────────────────┐
│  RANDOM KEY WITH IDEMPOTENCY                                        │
│                                                                      │
│  Use case: High throughput, ordering not required                  │
│  Key: null (uses Sticky Partitioner)                               │
│  Idempotency: Include unique ID in message value                   │
│                                                                      │
│  Consumer deduplicates using Redis/DB:                             │
│  if not redis.setnx(f"processed:{idempotency_key}", "1"):          │
│      return  # Already processed                                   │
│  process(message)                                                   │
│                                                                      │
│  + Maximum throughput                                               │
│  + Perfect load balance                                            │
│  + Handles duplicates                                               │
│  - Additional storage for dedup state                              │
│  - No ordering guarantees                                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Handling Hot Partitions / Обработка горячих партиций

### Problem: Key Skew / Проблема: Неравномерность ключей

```
┌─────────────────────────────────────────────────────────────────────┐
│  HOT PARTITION PROBLEM                                              │
│                                                                      │
│  Scenario: E-commerce during Black Friday                          │
│  Key: customer_id                                                   │
│                                                                      │
│  Partition 0: 10,000 messages   (normal customers)                 │
│  Partition 1: 15,000 messages   (normal customers)                 │
│  Partition 2: 500,000 messages  (celebrity with flash sale!)       │
│  Partition 3: 12,000 messages   (normal customers)                 │
│                                                                      │
│  Result:                                                            │
│  • Consumer of P2 overwhelmed                                       │
│  • Lag builds up                                                    │
│  • End-to-end latency increases                                    │
└─────────────────────────────────────────────────────────────────────┘
```

### Solution 1: Key Salting / Решение 1: Соление ключей

```python
import random

def salted_key(entity_id: str, num_salt_buckets: int = 10) -> str:
    """
    Add random salt to distribute hot keys across partitions.
    Trade-off: Loses ordering guarantee for entity.
    """
    salt = random.randint(0, num_salt_buckets - 1)
    return f"{entity_id}:{salt}"

# Original: All orders for celebrity-123 → same partition
key = "celebrity-123"

# Salted: Orders distributed across 10 partitions
key = salted_key("celebrity-123")  # "celebrity-123:7"
key = salted_key("celebrity-123")  # "celebrity-123:2"

# Consumer must aggregate results from all salt buckets
```

### Solution 2: Separate Topics / Решение 2: Отдельные топики

```
┌─────────────────────────────────────────────────────────────────────┐
│  SEPARATE TOPICS FOR HOT ENTITIES                                   │
│                                                                      │
│  Topic: orders (normal traffic, 4 partitions)                      │
│  Topic: orders-high-volume (celebrity customers, 8 partitions)     │
│                                                                      │
│  Producer routes:                                                   │
│  if customer.is_high_volume:                                        │
│      topic = "orders-high-volume"                                   │
│      key = salted_key(customer_id)                                  │
│  else:                                                              │
│      topic = "orders"                                               │
│      key = customer_id                                              │
└─────────────────────────────────────────────────────────────────────┘
```

### Solution 3: Dynamic Partitioner / Решение 3: Динамический партиционер

```python
class AdaptivePartitioner:
    """
    Monitor partition lag and avoid overloaded partitions.
    """

    def __init__(self, admin_client: AdminClient):
        self.admin_client = admin_client
        self.lag_cache = {}
        self.cache_ttl = 60  # seconds

    def __call__(self, key, all_partitions, available_partitions):
        self._refresh_lag_if_needed()
        target = hash(key) % len(all_partitions)

        if self._is_overloaded(target):
            target = self._find_least_loaded(all_partitions)

        return target

    def _is_overloaded(self, partition: int) -> bool:
        threshold = 100_000  # messages
        return self.lag_cache.get(partition, 0) > threshold

    def _find_least_loaded(self, partitions: list) -> int:
        return min(partitions, key=lambda p: self.lag_cache.get(p, 0))
```

---

## Partition Rebalancing / Ребалансировка партиций

### What Triggers Rebalancing / Что вызывает ребалансировку

1. Consumer joins group
2. Consumer leaves group (crash, shutdown)
3. Consumer fails heartbeat (`session.timeout.ms`)
4. Consumer exceeds `max.poll.interval.ms`
5. Partition count changes (admin operation)
6. Consumer subscribes to new topic pattern

### Impact of Adding Partitions / Влияние добавления партиций

```
┌─────────────────────────────────────────────────────────────────────┐
│  PARTITION INCREASE WARNING                                         │
│                                                                      │
│  BEFORE: 4 partitions                                               │
│  hash("key-A") % 4 = 2                                              │
│  hash("key-B") % 4 = 1                                              │
│                                                                      │
│  AFTER: 8 partitions                                                │
│  hash("key-A") % 8 = 6  ← DIFFERENT!                               │
│  hash("key-B") % 8 = 1  ← Same (lucky)                             │
│                                                                      │
│  Consequences:                                                      │
│  • Keys redistributed to different partitions                      │
│  • Ordering guarantee broken for existing keys                     │
│  • New messages for "key-A" go to P6, old in P2                    │
│                                                                      │
│  Mitigation:                                                        │
│  • Plan partition count upfront                                     │
│  • Use consistent hashing if order critical                        │
│  • Drain topic before partition change                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Best Practices Summary / Итоговые рекомендации

```
┌─────────────────────────────────────────────────────────────────────┐
│  PARTITION KEY BEST PRACTICES                                       │
│                                                                      │
│  1. CHOOSE KEY BASED ON ORDERING NEEDS                              │
│     • Need ordering? → Use entity-based key                        │
│     • No ordering? → Use null key (Sticky Partitioner)             │
│                                                                      │
│  2. PLAN FOR KEY CARDINALITY                                        │
│     • Keys should have high cardinality for distribution           │
│     • Avoid keys with few unique values                            │
│                                                                      │
│  3. CONSIDER MULTI-TENANCY                                          │
│     • Include tenant_id in key for isolation                       │
│     • Use composite keys: {tenant}:{entity}                        │
│                                                                      │
│  4. HANDLE HOT KEYS                                                 │
│     • Monitor partition lag                                         │
│     • Use key salting for known hot keys                           │
│     • Consider separate topics for high-volume entities            │
│                                                                      │
│  5. PLAN PARTITION COUNT                                            │
│     • Start with partitions = expected_max_consumers               │
│     • Leave room for growth (can add, can't remove)                │
│     • Typical: 6-12 for most use cases                             │
│                                                                      │
│  6. TEST KEY DISTRIBUTION                                           │
│     • Before production: verify even distribution                  │
│     • Monitor: partition lag should be similar across partitions   │
└─────────────────────────────────────────────────────────────────────┘
```

## Связано с
- [[Kafka]]
- [[Consumer-Groups]]

## Ресурсы
- [Kafka Partitioner Interface](https://kafka.apache.org/documentation/#producerconfigs_partitioner.class)
- [KIP-480: Sticky Partitioner](https://cwiki.apache.org/confluence/display/KAFKA/KIP-480)
- [Kafka Producer Best Practices](https://docs.confluent.io/platform/current/clients/producer.html)
- [Handling Hot Partitions](https://www.confluent.io/blog/how-choose-number-topics-partitions-kafka-cluster/)

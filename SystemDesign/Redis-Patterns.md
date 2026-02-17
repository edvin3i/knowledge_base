---
tags:
  - system-design
  - redis
  - caching
created: 2026-02-17
---

# Redis Caching Patterns and Data Structures
# Паттерны кэширования и структуры данных Redis

> **Reading time:** ~18 min | **Время чтения:** ~18 мин

## Что это

Паттерны кэширования Redis (Cache-Aside, Write-Through, Write-Behind, Read-Through), политики вытеснения (LRU, LFU, noeviction), структуры данных (String, Hash, List, Set, Sorted Set, Stream), Pub/Sub, Streams с consumer groups, распределённые блокировки (Redlock), Redis Cluster.

Redis is an in-memory data structure store used as a cache, message broker, and database. This document covers the essential caching patterns, eviction policies, and advanced features like Pub/Sub and Streams.

Redis — это хранилище структур данных в памяти, используемое как кэш, брокер сообщений и база данных. Этот документ рассматривает основные паттерны кэширования, политики вытеснения и продвинутые возможности вроде Pub/Sub и Streams.

---

## Caching Patterns / Паттерны кэширования

### Cache-Aside (Lazy Loading) / Кэш в стороне

The most common pattern: application manages cache and database separately.

Самый распространённый паттерн: приложение управляет кэшем и базой данных отдельно.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CACHE-ASIDE PATTERN                          │
│                                                                      │
│  READ FLOW:                                                         │
│                                                                      │
│     Application                                                     │
│          │                                                          │
│          │ 1. Check cache                                           │
│          ▼                                                          │
│     ┌─────────┐                                                     │
│     │  Redis  │                                                     │
│     │  Cache  │                                                     │
│     └────┬────┘                                                     │
│          │                                                          │
│     ┌────┴────────────────────────────────────────┐                │
│     │                                              │                │
│     ▼ HIT                                         ▼ MISS           │
│  Return data                              2. Query database        │
│                                                   │                 │
│                                                   ▼                 │
│                                           ┌────────────┐            │
│                                           │ PostgreSQL │            │
│                                           └─────┬──────┘            │
│                                                 │                   │
│                                        3. Store in cache            │
│                                                 │                   │
│                                                 ▼                   │
│                                           ┌─────────┐               │
│                                           │  Redis  │               │
│                                           └─────────┘               │
│                                                 │                   │
│                                        4. Return data               │
│                                                 ▼                   │
│                                           Application               │
│                                                                      │
│  WRITE FLOW:                                                        │
│                                                                      │
│     Application ──► PostgreSQL                                      │
│          │              │                                           │
│          │              │ 1. Write to DB                            │
│          │              ▼                                           │
│          └─────────► Invalidate cache                               │
│                      (delete key)                                   │
└─────────────────────────────────────────────────────────────────────┘
```

```python
# Cache-Aside implementation
import redis
import json
from typing import Optional

redis_client = redis.from_url("redis://localhost:6379")

def get_user(user_id: str) -> Optional[dict]:
    # 1. Check cache first
    cache_key = f"user:{user_id}"
    cached = redis_client.get(cache_key)

    if cached:
        return json.loads(cached)  # Cache HIT

    # 2. Cache MISS - query database
    user = db.query("SELECT * FROM users WHERE id = %s", user_id)

    if user:
        # 3. Store in cache with TTL
        redis_client.setex(
            cache_key,
            300,  # 5 minutes TTL
            json.dumps(user)
        )

    return user

def update_user(user_id: str, data: dict):
    # 1. Update database
    db.execute("UPDATE users SET ... WHERE id = %s", user_id)

    # 2. Invalidate cache (don't update - delete!)
    redis_client.delete(f"user:{user_id}")
```

**Pros / Плюсы:**
- Simple to implement / Просто реализовать
- Only requested data is cached / Кэшируются только запрошенные данные
- Cache failures don't break the system / Сбои кэша не ломают систему

**Cons / Минусы:**
- Cache miss = 3 network calls / Промах кэша = 3 сетевых вызова
- Stale data possible between write and invalidate / Возможны устаревшие данные

---

### Write-Through / Сквозная запись

Write to cache and database synchronously.

Синхронная запись в кэш и базу данных.

```
┌─────────────────────────────────────────────────────────────────────┐
│                       WRITE-THROUGH PATTERN                          │
│                                                                      │
│  WRITE FLOW:                                                        │
│                                                                      │
│     Application                                                     │
│          │                                                          │
│          │ 1. Write request                                         │
│          ▼                                                          │
│     ┌──────────────────────────────────────────┐                   │
│     │           Cache Service Layer             │                   │
│     └──────────────────────────────────────────┘                   │
│          │                    │                                     │
│          │ 2a. Write cache    │ 2b. Write DB                       │
│          ▼                    ▼                                     │
│     ┌─────────┐         ┌────────────┐                             │
│     │  Redis  │         │ PostgreSQL │                             │
│     │  Cache  │         │            │                             │
│     └─────────┘         └────────────┘                             │
│                                                                      │
│  Both writes must succeed (transaction-like)                        │
│                                                                      │
│  READ FLOW:                                                         │
│                                                                      │
│     Application ──► Redis (always cache hit)                       │
│                                                                      │
│  Note: Typically implemented by cache service,                      │
│  not application directly                                           │
└─────────────────────────────────────────────────────────────────────┘
```

```python
# Write-Through implementation
class WriteThoughCache:
    def write(self, key: str, value: dict):
        # Transaction-like: both must succeed
        try:
            # 1. Write to database
            db.execute("INSERT INTO data VALUES (%s, %s)", key, value)

            # 2. Write to cache
            redis_client.set(f"data:{key}", json.dumps(value))

        except Exception as e:
            # Rollback if either fails
            db.rollback()
            redis_client.delete(f"data:{key}")
            raise

    def read(self, key: str) -> dict:
        # Always read from cache (guaranteed fresh)
        return json.loads(redis_client.get(f"data:{key}"))
```

**Pros / Плюсы:**
- Cache always has fresh data / Кэш всегда содержит свежие данные
- Reads are fast (always cache hit) / Чтения быстрые (всегда попадание)

**Cons / Минусы:**
- Write latency increases / Латентность записи увеличивается
- Complex failure handling / Сложная обработка сбоев
- Unused data fills cache / Неиспользуемые данные заполняют кэш

---

### Write-Behind (Write-Back) / Отложенная запись

Write to cache immediately, sync to database asynchronously.

Немедленная запись в кэш, асинхронная синхронизация с базой данных.

```
┌─────────────────────────────────────────────────────────────────────┐
│                       WRITE-BEHIND PATTERN                           │
│                                                                      │
│  WRITE FLOW:                                                        │
│                                                                      │
│     Application                                                     │
│          │                                                          │
│          │ 1. Write request                                         │
│          ▼                                                          │
│     ┌─────────┐                                                     │
│     │  Redis  │ ◄── Immediate ACK to application                   │
│     │  Cache  │                                                     │
│     └────┬────┘                                                     │
│          │                                                          │
│          │ 2. Async write (batched)                                 │
│          │    Background worker                                     │
│          ▼                                                          │
│     ┌────────────────────────────────────────────────┐             │
│     │              Write Queue (Redis List)          │             │
│     └────────────────────────────────────────────────┘             │
│          │                                                          │
│          │ 3. Batch flush                                           │
│          ▼                                                          │
│     ┌────────────┐                                                  │
│     │ PostgreSQL │                                                  │
│     │            │                                                  │
│     └────────────┘                                                  │
│                                                                      │
│  Typical batch interval: 100ms - 1s                                 │
│  Batch size: 100-1000 writes                                        │
└─────────────────────────────────────────────────────────────────────┘
```

```python
# Write-Behind with Redis List as queue
class WriteBehindCache:
    def write(self, key: str, value: dict):
        # 1. Write to cache (immediate)
        redis_client.set(f"data:{key}", json.dumps(value))

        # 2. Queue for async DB write
        redis_client.lpush("db_write_queue", json.dumps({
            "key": key,
            "value": value,
            "timestamp": time.time()
        }))

    # Background worker (separate process)
    def flush_to_db(self, batch_size=100):
        batch = []

        # Collect batch
        for _ in range(batch_size):
            item = redis_client.rpop("db_write_queue")
            if not item:
                break
            batch.append(json.loads(item))

        if batch:
            # Bulk insert to database
            db.execute_many(
                "INSERT INTO data VALUES (%s, %s)",
                [(item["key"], item["value"]) for item in batch]
            )
```

**Pros / Плюсы:**
- Fastest write latency / Самая низкая латентность записи
- Batching improves DB throughput / Батчинг улучшает пропускную способность БД

**Cons / Минусы:**
- Data loss risk if cache fails / Риск потери данных при сбое кэша
- Complex recovery / Сложное восстановление
- Eventual consistency / Согласованность в конечном счёте

---

### Read-Through / Сквозное чтение

Cache manages data fetching from database.

Кэш управляет получением данных из базы данных.

```
┌─────────────────────────────────────────────────────────────────────┐
│                       READ-THROUGH PATTERN                           │
│                                                                      │
│     Application                                                     │
│          │                                                          │
│          │ 1. Request data                                          │
│          ▼                                                          │
│     ┌─────────────────────────────────────┐                        │
│     │       Cache Service Layer           │                        │
│     │  (handles DB fetching internally)   │                        │
│     └─────────────────────────────────────┘                        │
│          │                    │                                     │
│          │                    │ Cache MISS                          │
│          │                    ▼                                     │
│          │              ┌────────────┐                              │
│          │              │ PostgreSQL │                              │
│          │              └─────┬──────┘                              │
│          │                    │                                     │
│          │     ◄──────────────┘ Auto-populate cache                │
│          │                                                          │
│          ▼                                                          │
│     Return data                                                     │
│                                                                      │
│  Difference from Cache-Aside:                                       │
│  • Application only talks to cache layer                            │
│  • Cache layer handles DB interaction                               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Eviction Policies / Политики вытеснения

When Redis reaches memory limit, it must evict data. Policy determines what to remove.

Когда Redis достигает лимита памяти, он должен вытеснять данные. Политика определяет что удалять.

```
┌─────────────────────────────────────────────────────────────────────┐
│                       REDIS EVICTION POLICIES                        │
│                                                                      │
│  maxmemory-policy setting in redis.conf                             │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  noeviction (default)                                        │    │
│  │  ───────────────────────────────────────────────────────────│    │
│  │  • Returns error when memory limit reached                   │    │
│  │  • Use for: Celery broker (NO task loss!)                    │    │
│  │  • Polyvision: redis-celery uses this                        │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  allkeys-lru (Least Recently Used)                           │    │
│  │  ───────────────────────────────────────────────────────────│    │
│  │  • Evicts least recently used keys                           │    │
│  │  • Best for: general caching                                 │    │
│  │  • Polyvision: redis-cache uses this                         │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  allkeys-lfu (Least Frequently Used)                         │    │
│  │  ───────────────────────────────────────────────────────────│    │
│  │  • Evicts keys accessed least often                          │    │
│  │  • Better for: workloads with hot/cold data                  │    │
│  │  • Added in Redis 4.0                                        │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  volatile-lru / volatile-lfu / volatile-ttl                  │    │
│  │  ───────────────────────────────────────────────────────────│    │
│  │  • Only evicts keys with EXPIRE set                          │    │
│  │  • Protects keys without TTL                                 │    │
│  │  • volatile-ttl: evict keys closest to expiry                │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  allkeys-random / volatile-random                            │    │
│  │  ───────────────────────────────────────────────────────────│    │
│  │  • Random eviction                                           │    │
│  │  • Use when all keys have equal importance                   │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### Redis Configuration / Конфигурация Redis

```bash
# redis-cache.conf (for API caching)
maxmemory 4gb
maxmemory-policy allkeys-lru
maxmemory-samples 10  # LRU approximation accuracy

# redis-celery.conf (for task broker)
maxmemory 2gb
maxmemory-policy noeviction  # CRITICAL: never lose tasks!
```

---

## Redis Data Structures / Структуры данных Redis

```
┌─────────────────────────────────────────────────────────────────────┐
│                     REDIS DATA STRUCTURES                            │
│                                                                      │
│  STRING                                                             │
│  ────────                                                           │
│  SET key "value"                                                    │
│  GET key                                                            │
│  INCR counter                                                       │
│  Use: Sessions, counters, simple caching                            │
│                                                                      │
│  HASH                                                               │
│  ────                                                               │
│  HSET user:1 name "John" age 30                                     │
│  HGET user:1 name                                                   │
│  HGETALL user:1                                                     │
│  Use: Objects with fields, user profiles                            │
│                                                                      │
│  LIST                                                               │
│  ────                                                               │
│  LPUSH queue "task1"                                                │
│  RPOP queue                                                         │
│  LRANGE queue 0 -1                                                  │
│  Use: Queues, recent items, activity feeds                          │
│                                                                      │
│  SET                                                                │
│  ───                                                                │
│  SADD tags "redis" "cache"                                          │
│  SISMEMBER tags "redis"                                             │
│  SINTER tags1 tags2                                                 │
│  Use: Unique items, tags, set operations                            │
│                                                                      │
│  SORTED SET (ZSET)                                                  │
│  ─────────────────                                                  │
│  ZADD leaderboard 100 "player1" 95 "player2"                        │
│  ZRANGE leaderboard 0 10 WITHSCORES                                 │
│  ZRANK leaderboard "player1"                                        │
│  Use: Leaderboards, time-sorted data, priority queues               │
│                                                                      │
│  STREAM                                                             │
│  ──────                                                             │
│  XADD events * type "click" user "123"                              │
│  XREAD STREAMS events 0                                             │
│  XREADGROUP GROUP consumers consumer1 STREAMS events >              │
│  Use: Event streaming, log processing                               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Pub/Sub Pattern / Паттерн Pub/Sub

Real-time messaging where publishers send to channels, subscribers receive.

Обмен сообщениями в реальном времени: издатели отправляют в каналы, подписчики получают.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         REDIS PUB/SUB                                │
│                                                                      │
│  ┌─────────────┐                                                    │
│  │ Publisher 1 │──┐                                                 │
│  └─────────────┘  │                                                 │
│                   │  PUBLISH channel message                        │
│  ┌─────────────┐  │                                                 │
│  │ Publisher 2 │──┼────────────────────────┐                       │
│  └─────────────┘  │                        │                        │
│                   │         ┌──────────────▼──────────────┐         │
│                   └────────►│         Redis               │         │
│                             │  ┌─────────────────────┐    │         │
│                             │  │ channel: "events"   │    │         │
│                             │  └─────────────────────┘    │         │
│                             └──────────────┬──────────────┘         │
│                                            │                        │
│                            ┌───────────────┼───────────────┐        │
│                            │               │               │        │
│                            ▼               ▼               ▼        │
│                     ┌────────────┐  ┌────────────┐  ┌────────────┐  │
│                     │Subscriber 1│  │Subscriber 2│  │Subscriber N│  │
│                     └────────────┘  └────────────┘  └────────────┘  │
│                                                                      │
│  Characteristics:                                                   │
│  • Fire and forget (no persistence)                                 │
│  • No message history                                               │
│  • If subscriber offline, messages lost                             │
│  • Use for: Cache invalidation, notifications                       │
└─────────────────────────────────────────────────────────────────────┘
```

```python
# Pub/Sub example
import redis

# Publisher
def publish_cache_invalidation(key: str):
    redis_client.publish("cache_invalidation", key)

# Subscriber (separate process)
def subscribe_to_invalidations():
    pubsub = redis_client.pubsub()
    pubsub.subscribe("cache_invalidation")

    for message in pubsub.listen():
        if message["type"] == "message":
            key = message["data"].decode()
            local_cache.delete(key)
            print(f"Invalidated: {key}")

# Use case: Multi-instance cache invalidation
# When one instance updates data, all instances
# receive invalidation message
```

---

## Redis Streams / Redis Streams

Persistent, consumer-group-aware message streaming (like Kafka).

Персистентный стриминг сообщений с группами потребителей (как Kafka).

```
┌─────────────────────────────────────────────────────────────────────┐
│                         REDIS STREAMS                                │
│                                                                      │
│  STREAM: events                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ ID: 1673532000000-0  │ ID: 1673532000001-0  │ ...            │    │
│  │ type: "click"        │ type: "purchase"     │                │    │
│  │ user: "123"          │ user: "456"          │                │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  CONSUMER GROUPS                                                    │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Group: analytics-processors                                 │    │
│  │                                                               │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │    │
│  │  │ Consumer 1   │  │ Consumer 2   │  │ Consumer 3   │       │    │
│  │  │ Last: -0     │  │ Last: -1     │  │ Last: -2     │       │    │
│  │  │ Pending: 2   │  │ Pending: 0   │  │ Pending: 1   │       │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘       │    │
│  │                                                               │    │
│  │  Each message delivered to exactly ONE consumer in group    │    │
│  │  Pending = unacknowledged messages                           │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  Key differences from Pub/Sub:                                      │
│  • Messages persist until trimmed                                   │
│  • Consumer groups enable load balancing                            │
│  • Acknowledgment required                                          │
│  • Message history accessible                                       │
└─────────────────────────────────────────────────────────────────────┘
```

```python
# Redis Streams example
import redis

redis_client = redis.from_url("redis://localhost:6379")

# Producer: Add event to stream
def add_event(event_type: str, data: dict):
    redis_client.xadd(
        "events",
        {
            "type": event_type,
            **data
        },
        maxlen=100000  # Trim to last 100k messages
    )

# Create consumer group (once)
try:
    redis_client.xgroup_create("events", "processors", id="0", mkstream=True)
except redis.ResponseError:
    pass  # Group already exists

# Consumer: Process events
def process_events(consumer_name: str):
    while True:
        # Read new messages for this consumer
        messages = redis_client.xreadgroup(
            groupname="processors",
            consumername=consumer_name,
            streams={"events": ">"},  # ">" = only new messages
            count=10,
            block=5000  # 5 second timeout
        )

        for stream, entries in messages:
            for entry_id, data in entries:
                try:
                    process_event(data)
                    # Acknowledge successful processing
                    redis_client.xack("events", "processors", entry_id)
                except Exception as e:
                    print(f"Failed: {entry_id}, will retry")
                    # Message stays in pending, can be reclaimed
```

### Streams vs Pub/Sub vs Lists / Сравнение Streams, Pub/Sub и Lists

| Feature | Pub/Sub | Lists | Streams |
|---------|---------|-------|---------|
| **Persistence** | No | Yes | Yes |
| **Consumer groups** | No | No | Yes |
| **Message replay** | No | Manual | Yes |
| **Acknowledgment** | No | No | Yes |
| **Blocking read** | Yes | Yes (BRPOP) | Yes |
| **Use case** | Notifications | Simple queues | Event streaming |

---

## Distributed Locking / Распределённая блокировка

Redis can implement distributed locks for coordination across services.

Redis может реализовать распределённые блокировки для координации между сервисами.

```
┌─────────────────────────────────────────────────────────────────────┐
│                      REDIS DISTRIBUTED LOCK                          │
│                                                                      │
│  REDLOCK ALGORITHM (Correct implementation)                         │
│                                                                      │
│  1. Get current time                                                │
│  2. Try to acquire lock in all N Redis instances                    │
│  3. Lock acquired if majority (N/2 + 1) succeeded                   │
│     AND elapsed time < lock validity                                │
│  4. If lock fails, release all instances                            │
│                                                                      │
│  SIMPLE LOCK (Single Redis, sufficient for many cases)              │
│                                                                      │
│     SET lock:resource unique_id NX PX 30000                         │
│     │            │          │   │  └── Expire in 30s (prevent deadlock)
│     │            │          │   └──── Only if Not eXists          │
│     │            │          └──────── Unique identifier (for safe release)
│     │            └─────────────────── Lock name                   │
│     └──────────────────────────────── Redis command               │
│                                                                      │
│  RELEASE: Only if we own the lock (Lua script for atomicity)       │
│                                                                      │
│  if redis.call("get", KEYS[1]) == ARGV[1] then                     │
│      return redis.call("del", KEYS[1])                              │
│  else                                                               │
│      return 0                                                        │
│  end                                                                 │
└─────────────────────────────────────────────────────────────────────┘
```

```python
# Distributed lock implementation
import redis
import uuid
import time

class RedisLock:
    def __init__(self, redis_client, name, timeout=30):
        self.redis = redis_client
        self.name = f"lock:{name}"
        self.timeout = timeout
        self.token = str(uuid.uuid4())

    def acquire(self, blocking=True, blocking_timeout=None):
        start = time.time()

        while True:
            # Try to acquire
            if self.redis.set(self.name, self.token, nx=True, px=self.timeout * 1000):
                return True

            if not blocking:
                return False

            if blocking_timeout and (time.time() - start) > blocking_timeout:
                return False

            time.sleep(0.1)  # Brief sleep before retry

    def release(self):
        # Lua script for atomic check-and-delete
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        self.redis.eval(script, 1, self.name, self.token)

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()

# Usage
with RedisLock(redis_client, "process-match-123") as lock:
    # Critical section - only one process can execute
    process_match("123")
```

---

## Redis Cluster / Redis Cluster

```
┌─────────────────────────────────────────────────────────────────────┐
│                        REDIS CLUSTER                                 │
│                                                                      │
│  Hash slots: 16384 slots distributed across nodes                   │
│                                                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │
│  │   Master 1  │    │   Master 2  │    │   Master 3  │             │
│  │ Slots 0-5460│    │Slots 5461-10922│ │Slots 10923-16383│          │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘             │
│         │                  │                  │                     │
│         ▼                  ▼                  ▼                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │
│  │  Replica 1  │    │  Replica 2  │    │  Replica 3  │             │
│  └─────────────┘    └─────────────┘    └─────────────┘             │
│                                                                      │
│  Key routing: slot = CRC16(key) mod 16384                           │
│                                                                      │
│  Hash tags: {user:123}.profile and {user:123}.settings              │
│             go to same slot (same node)                             │
│                                                                      │
│  Limitations:                                                       │
│  • Multi-key operations must be on same slot                        │
│  • Pub/Sub: messages go to all nodes                                │
│  • Transactions limited to same slot                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Interview Questions / Вопросы для интервью

**Q1: When would you choose Write-Behind over Write-Through caching?**

A: Write-Behind (write-back) is chosen when: (1) Write latency is critical - it returns immediately after cache write, (2) Database can handle batched writes more efficiently, (3) Brief data loss is acceptable (data in cache not yet synced). Write-Through is better when: (1) Data must be durable immediately, (2) Simpler recovery is needed, (3) Write latency is less critical than data safety. Write-Behind is common for analytics events, metrics, and non-critical writes.

**Q2: Explain the difference between Redis Pub/Sub and Streams. When would you use each?**

A: Pub/Sub is fire-and-forget: messages are delivered to connected subscribers instantly and not persisted. If a subscriber is offline, messages are lost. Use for: cache invalidation, real-time notifications. Streams persist messages, support consumer groups for load balancing, require acknowledgment, and allow message replay. Use for: event sourcing, job queues where message delivery guarantee is needed. Streams are like a simpler Kafka within Redis.

**Q3: Why does [[Polyvision]] use two Redis instances with different eviction policies?**

A: Polyvision separates concerns by purpose: (1) `redis-cache` uses `allkeys-lru` for API caching and sessions - when memory fills, least-recently-used data is evicted. This is safe because cache misses just mean slower queries. (2) `redis-celery` uses `noeviction` as Celery's task broker - when memory fills, Redis returns errors rather than silently dropping tasks. This prevents silent task loss which would cause matches to never complete processing. Different eviction policies match different data criticality.

## Связано с

- [[SQL-vs-NoSQL]]
- [[PV-Storage]]

## Ресурсы

- [Redis Documentation](https://redis.io/documentation)
- [Redis University](https://university.redis.com/)
- [Redis Caching Strategies](https://redis.io/docs/manual/patterns/)
- [Distributed Locks with Redis (Redlock)](https://redis.io/topics/distlock)
- [Redis Streams Introduction](https://redis.io/docs/data-types/streams/)
- [Designing Data-Intensive Applications - Martin Kleppmann](https://dataintensive.net/)

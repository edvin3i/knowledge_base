---
tags:
  - system-design
  - high-availability
  - idempotency
created: 2026-02-17
---

# Idempotency Patterns / Паттерны идемпотентности

> **Reading time:** ~15 min | **Время чтения:** ~15 мин

## Что это

Паттерны обеспечения идемпотентности в распределённых системах: SETNX-дедупликация, уникальные ограничения БД, векторы версий, Transactional Outbox, API Idempotency Key.

**Idempotency** means that performing the same operation multiple times produces the same result as performing it once.

**Идемпотентность** означает, что выполнение одной и той же операции несколько раз даёт тот же результат, что и однократное выполнение.

---

## Idempotent vs Non-Idempotent

```
┌─────────────────────────────────────────────────────────────────────┐
│  IDEMPOTENT vs NON-IDEMPOTENT                                      │
│                                                                      │
│  IDEMPOTENT OPERATIONS:                                             │
│  • GET /users/123          → Returns user (same every time)        │
│  • PUT /users/123 {name}   → Sets name (same result if repeated)   │
│  • DELETE /users/123       → Deletes user (already deleted = OK)   │
│  • SET key=value           → Same value regardless of calls        │
│                                                                      │
│  NON-IDEMPOTENT OPERATIONS:                                         │
│  • POST /users             → Creates new user each time!           │
│  • INCR counter            → Different result each time            │
│  • account.debit($100)     → Withdraws $100 each call!             │
│                                                                      │
│  Why it matters:                                                    │
│  Network failures → Retries → Duplicate requests                   │
│  If operation is idempotent → Safe to retry                        │
│  If NOT idempotent → May cause data corruption!                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Why Idempotency Matters / Почему идемпотентность важна

### The Duplicate Problem / Проблема дубликатов

```
┌─────────────────────────────────────────────────────────────────────┐
│  DUPLICATE REQUEST SCENARIOS                                        │
│                                                                      │
│  1. CLIENT TIMEOUT + RETRY                                          │
│     ┌────────┐         ┌────────┐                                  │
│     │ Client │──req───▶│ Server │ (processes request)              │
│     │        │   ✗ timeout       │                                  │
│     │        │──req───▶│        │ (processes AGAIN!)               │
│     │        │◀──resp──│        │                                  │
│     └────────┘         └────────┘                                  │
│     Result: Operation executed twice                               │
│                                                                      │
│  2. LOAD BALANCER RETRY                                            │
│     ┌────────┐    ┌────┐    ┌────────┐                            │
│     │ Client │───▶│ LB │───▶│Server 1│ (slow response)            │
│     │        │    │    │───▶│Server 2│ (retry to different node)  │
│     └────────┘    └────┘    └────────┘                            │
│     Result: Two servers process same request                       │
│                                                                      │
│  3. MESSAGE QUEUE REDELIVERY                                        │
│     ┌────────┐    ┌────────┐    ┌────────┐                        │
│     │Producer│───▶│  Queue │───▶│Consumer│ (crashes before ack)   │
│     │        │    │        │───▶│Consumer│ (redelivered!)         │
│     └────────┘    └────────┘    └────────┘                        │
│     Result: Message processed twice                                │
│                                                                      │
│  4. KAFKA REBALANCING                                               │
│     Consumer A processing message                                   │
│     → Rebalance triggered                                           │
│     → Consumer B assigned same partition                            │
│     → Consumer B reprocesses uncommitted messages                  │
│     Result: Duplicate processing during rebalance                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Idempotency Patterns / Паттерны идемпотентности

### Pattern 1: SETNX-Based Deduplication / Дедупликация через SETNX

```
┌─────────────────────────────────────────────────────────────────────┐
│  SETNX (SET if Not eXists) PATTERN                                 │
│                                                                      │
│  Concept: Use unique key to track processed requests               │
│                                                                      │
│  First request:                                                     │
│  ┌────────┐         ┌────────┐         ┌────────┐                 │
│  │ Client │──req───▶│ Server │──SETNX──▶│ Redis  │                 │
│  │        │  id=123 │        │ key=123  │ (OK)   │                 │
│  │        │         │process │         │        │                 │
│  │        │◀──resp──│        │         │        │                 │
│  └────────┘         └────────┘         └────────┘                 │
│                                                                      │
│  Duplicate request:                                                 │
│  ┌────────┐         ┌────────┐         ┌────────┐                 │
│  │ Client │──req───▶│ Server │──SETNX──▶│ Redis  │                 │
│  │        │  id=123 │        │ key=123  │(EXISTS)│                 │
│  │        │         │ SKIP   │◀─false──│        │                 │
│  │        │◀──resp──│        │         │        │                 │
│  └────────┘         └────────┘         └────────┘                 │
└─────────────────────────────────────────────────────────────────────┘
```

```python
import redis
from typing import Optional

class IdempotencyService:
    def __init__(self, redis_client: redis.Redis, ttl_seconds: int = 86400 * 7):
        self.redis = redis_client
        self.ttl = ttl_seconds

    def try_process(self, idempotency_key: str) -> bool:
        """
        Returns True if this is the first time seeing this key.
        Returns False if duplicate (already processed).
        """
        # SETNX + EXPIRE atomically
        result = self.redis.set(
            f"idem:{idempotency_key}",
            "1",
            nx=True,  # Only set if not exists
            ex=self.ttl  # Expiry in seconds
        )
        return result is not None

    def mark_completed(self, idempotency_key: str, result: str):
        """Store the result for duplicate requests."""
        self.redis.setex(
            f"idem:{idempotency_key}",
            self.ttl,
            result
        )

    def get_result(self, idempotency_key: str) -> Optional[str]:
        """Get stored result for duplicate request."""
        return self.redis.get(f"idem:{idempotency_key}")


# Usage in API endpoint
idempotency_service = IdempotencyService(redis.Redis())

async def create_payment(payment_request, idempotency_key: str):
    # Check if already processed
    if not idempotency_service.try_process(idempotency_key):
        # Return cached result
        return idempotency_service.get_result(idempotency_key)

    # Process payment
    result = await payment_processor.charge(payment_request)

    # Store result for future duplicates
    idempotency_service.mark_completed(idempotency_key, result)

    return result
```

### Pattern 2: Database Unique Constraint / Уникальное ограничение БД

```
┌─────────────────────────────────────────────────────────────────────┐
│  DATABASE UNIQUE CONSTRAINT PATTERN                                 │
│                                                                      │
│  Table schema:                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ CREATE TABLE payments (                                      │   │
│  │     id SERIAL PRIMARY KEY,                                   │   │
│  │     idempotency_key VARCHAR(255) UNIQUE NOT NULL,           │   │
│  │     amount DECIMAL(10,2),                                    │   │
│  │     status VARCHAR(50),                                      │   │
│  │     created_at TIMESTAMP DEFAULT NOW()                      │   │
│  │ );                                                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Insert with conflict handling:                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ INSERT INTO payments (idempotency_key, amount, status)       │   │
│  │ VALUES ($1, $2, $3)                                          │   │
│  │ ON CONFLICT (idempotency_key)                                │   │
│  │ DO NOTHING                                                    │   │
│  │ RETURNING *;                                                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  If duplicate: INSERT ignored, no error, no duplicate row          │
└─────────────────────────────────────────────────────────────────────┘
```

```python
async def create_payment_db(payment: PaymentRequest) -> Payment:
    async with db.transaction():
        # Try to insert
        result = await db.execute("""
            INSERT INTO payments (idempotency_key, amount, status)
            VALUES ($1, $2, 'pending')
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING *
        """, payment.idempotency_key, payment.amount)

        if result:
            # New payment, process it
            payment_record = result
            await process_payment(payment_record)
            return payment_record
        else:
            # Duplicate, return existing
            existing = await db.fetchone("""
                SELECT * FROM payments WHERE idempotency_key = $1
            """, payment.idempotency_key)
            return existing
```

### Pattern 3: Version Vectors / Векторы версий

```
┌─────────────────────────────────────────────────────────────────────┐
│  VERSION VECTOR PATTERN                                             │
│                                                                      │
│  Concept: Track version with each update, reject stale updates     │
│                                                                      │
│  Record: { id: 1, name: "Alice", version: 5 }                      │
│                                                                      │
│  Update attempt 1 (version 5 → 6):                                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ UPDATE users                                                 │   │
│  │ SET name = 'Alice Smith', version = version + 1             │   │
│  │ WHERE id = 1 AND version = 5;                               │   │
│  │ -- Succeeds: 1 row affected                                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Duplicate update attempt (version 5 → 6, but version is now 6):   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ UPDATE users                                                 │   │
│  │ SET name = 'Alice Smith', version = version + 1             │   │
│  │ WHERE id = 1 AND version = 5;                               │   │
│  │ -- Fails: 0 rows affected (version is 6, not 5)            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Also called: Optimistic Locking                                   │
└─────────────────────────────────────────────────────────────────────┘
```

### Pattern 4: Exactly-Once with Outbox / Exactly-Once с Outbox

```
┌─────────────────────────────────────────────────────────────────────┐
│  TRANSACTIONAL OUTBOX PATTERN                                       │
│                                                                      │
│  Problem: Need to update DB AND send message atomically            │
│                                                                      │
│  Wrong approach:                                                    │
│  1. Update DB                                                       │
│  2. Send message                                                    │
│  → If crash between 1 and 2: DB updated, message lost             │
│                                                                      │
│  Outbox solution:                                                   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  SINGLE TRANSACTION:                                         │   │
│  │  1. Update business table                                    │   │
│  │  2. Insert into outbox table                                 │   │
│  │  3. COMMIT                                                    │   │
│  │                                                               │   │
│  │  SEPARATE PROCESS (Outbox Relay):                           │   │
│  │  1. Poll outbox table for unsent messages                   │   │
│  │  2. Send to message broker                                   │   │
│  │  3. Mark as sent (or delete)                                │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Tables:                                                            │
│  ┌──────────────────┐    ┌──────────────────────────────────┐     │
│  │ orders           │    │ outbox                            │     │
│  │ ────────────────│    │ ───────────────────────────────── │     │
│  │ id               │    │ id                                │     │
│  │ customer_id      │    │ aggregate_type  (e.g., "order")  │     │
│  │ total            │    │ aggregate_id    (e.g., order.id) │     │
│  │ status           │    │ event_type      (e.g., "created")│     │
│  │ created_at       │    │ payload         (JSON)           │     │
│  └──────────────────┘    │ created_at                        │     │
│                          │ sent_at         (NULL = not sent)│     │
│                          └──────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘
```

```python
async def create_order_with_outbox(order_data: dict):
    async with db.transaction() as tx:
        # 1. Insert order
        order = await tx.execute("""
            INSERT INTO orders (customer_id, total, status)
            VALUES ($1, $2, 'pending')
            RETURNING *
        """, order_data['customer_id'], order_data['total'])

        # 2. Insert into outbox (same transaction!)
        await tx.execute("""
            INSERT INTO outbox (aggregate_type, aggregate_id, event_type, payload)
            VALUES ('order', $1, 'order_created', $2)
        """, order['id'], json.dumps({
            'order_id': order['id'],
            'customer_id': order['customer_id'],
            'total': str(order['total'])
        }))

        # 3. Transaction commits atomically

    return order


# Outbox relay (separate process)
async def outbox_relay():
    while True:
        messages = await db.fetch("""
            SELECT * FROM outbox
            WHERE sent_at IS NULL
            ORDER BY created_at
            LIMIT 100
            FOR UPDATE SKIP LOCKED
        """)

        for msg in messages:
            await kafka_producer.send(
                topic=f"events.{msg['aggregate_type']}",
                value=msg['payload']
            )
            await db.execute("""
                UPDATE outbox SET sent_at = NOW() WHERE id = $1
            """, msg['id'])

        await asyncio.sleep(1)
```

---

## API Idempotency / Идемпотентность API

### Idempotency Key Header / Заголовок ключа идемпотентности

```
┌─────────────────────────────────────────────────────────────────────┐
│  IDEMPOTENCY KEY IN HTTP API                                        │
│                                                                      │
│  Request:                                                           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ POST /v1/payments                                            │   │
│  │ Idempotency-Key: 8f14e45f-ceea-4e6a-a156-4e8c00a1e4f2       │   │
│  │ Content-Type: application/json                               │   │
│  │                                                               │   │
│  │ {                                                             │   │
│  │   "amount": 1000,                                            │   │
│  │   "currency": "USD",                                         │   │
│  │   "customer_id": "cus_123"                                   │   │
│  │ }                                                             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  First call:                                                        │
│  → Process payment                                                  │
│  → Store (key, response) in Redis                                  │
│  → Return 200 OK with payment result                               │
│                                                                      │
│  Retry with same key:                                               │
│  → Find key in Redis                                                │
│  → Return cached response (same 200 OK)                            │
│  → No duplicate charge!                                             │
│                                                                      │
│  Best practices:                                                    │
│  • Client generates UUID                                            │
│  • Key should be unique per operation intent                       │
│  • TTL: 24-48 hours typical                                        │
│  • Store full response (not just "processed" flag)                 │
└─────────────────────────────────────────────────────────────────────┘
```

### Implementation Example / Пример реализации

```python
from fastapi import FastAPI, Header, HTTPException
import redis
import json

app = FastAPI()
redis_client = redis.Redis()
IDEMPOTENCY_TTL = 86400  # 24 hours

@app.post("/v1/payments")
async def create_payment(
    payment: PaymentRequest,
    idempotency_key: str = Header(None, alias="Idempotency-Key")
):
    if not idempotency_key:
        raise HTTPException(400, "Idempotency-Key header required")

    cache_key = f"idem:payment:{idempotency_key}"

    # Check for existing response
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # Try to acquire lock for this key
    lock_acquired = redis_client.set(
        f"{cache_key}:lock",
        "1",
        nx=True,
        ex=30  # 30 second lock
    )

    if not lock_acquired:
        # Another request is processing
        raise HTTPException(409, "Request already in progress")

    try:
        # Process payment
        result = await payment_processor.charge(payment)

        # Cache response
        response = {
            "payment_id": result.id,
            "status": result.status,
            "amount": payment.amount
        }
        redis_client.setex(cache_key, IDEMPOTENCY_TTL, json.dumps(response))

        return response
    finally:
        # Release lock
        redis_client.delete(f"{cache_key}:lock")
```

---

## Summary / Итоги

```
┌─────────────────────────────────────────────────────────────────────┐
│  IDEMPOTENCY PATTERNS SUMMARY                                       │
│                                                                      │
│  Pattern           │ Use When                                       │
│  ─────────────────┼─────────────────────────────────────────────── │
│  SETNX (Redis)    │ Fast, distributed, ephemeral tracking          │
│  DB Unique        │ Persistent, transactional guarantee            │
│  Version Vectors  │ Optimistic concurrency control                 │
│  Outbox           │ DB + Message broker atomic operations          │
│                                                                      │
│  Key Generation:                                                    │
│  • Client-generated UUID for API calls                             │
│  • Message ID for queue messages                                    │
│  • Composite key: {entity}:{operation}:{timestamp}                 │
│                                                                      │
│  TTL Considerations:                                                │
│  • Too short: May not catch delayed retries                        │
│  • Too long: Storage costs, privacy concerns                       │
│  • Typical: 24-48 hours for API, 7 days for async processing      │
│                                                                      │
│  Testing:                                                           │
│  • Send same request twice → verify same response                  │
│  • Kill process mid-operation → verify no duplicates on retry      │
│  • Simulate network partitions → verify idempotency holds          │
└─────────────────────────────────────────────────────────────────────┘
```

## Связано с

- [[HA-Patterns]]
- [[Exactly-Once]]

## Ресурсы

- [Stripe Idempotent Requests](https://stripe.com/docs/api/idempotent_requests)
- [Designing Data-Intensive Applications](https://dataintensive.net/) -- Chapter 9
- [Transactional Outbox Pattern](https://microservices.io/patterns/data/transactional-outbox.html)
- [AWS Building Idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)

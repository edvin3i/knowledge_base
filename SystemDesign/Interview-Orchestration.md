---
tags:
  - system-design
  - orchestration
  - interview
created: 2026-02-17
---

# Вопросы для интервью по оркестрации

## Что это
Набор из 25 вопросов (Junior -> Senior) по теме workflow orchestration: фундаментальные концепции, [[Temporal]], [[Airflow]], [[Conductor]], проектирование систем и вопросы специфичные для [[Polyvision]].

## Category 1: Fundamentals / Основы

### Q1: What is workflow orchestration?
**Что такое оркестрация рабочих процессов?**

**Answer / Ответ:**

Workflow orchestration is the automated coordination and management of complex, multi-step processes across distributed systems.

Оркестрация рабочих процессов -- это автоматизированная координация и управление сложными многошаговыми процессами в распределённых системах.

**Key aspects / Ключевые аспекты:**
- Central coordination of multiple services
- State management and persistence
- Failure handling and retries
- Visibility into workflow progress

---

### Q2: What's the difference between orchestration and choreography?
**В чём разница между оркестрацией и хореографией?**

**Answer / Ответ:**

| Orchestration | Choreography |
|---------------|--------------|
| Central coordinator controls flow | Services react to events independently |
| Explicit workflow definition | Implicit flow through event chains |
| Easier to track/debug | Harder to trace full flow |
| Coordinator is SPOF | No single point of failure |
| Better for complex logic | Better for simple event chains |

**When to use / Когда использовать:**
- Choreography: 2-3 loosely coupled services
- Orchestration: 5+ services, complex business logic

---

### Q3: What is a DAG and why is it used in workflow systems?
**Что такое DAG и зачем он используется в системах workflow?**

**Answer / Ответ:**

**DAG = Directed Acyclic Graph**
DAG = Направленный ациклический граф

```
Directed: Tasks have clear upstream/downstream relationships
Acyclic: No circular dependencies (prevents infinite loops)
Graph: Multiple paths and branches allowed
```

**Why DAGs / Зачем DAG:**
- Clear dependency visualization
- Deterministic execution order
- Parallel execution of independent branches
- Easy to detect cycles at definition time

---

## Category 2: [[Temporal]]

### Q4: What is Event Sourcing and how does [[Temporal]] use it?
**Что такое Event Sourcing и как [[Temporal]] его использует?**

**Answer / Ответ:**

Event Sourcing stores state as a sequence of events rather than current state.

Event Sourcing хранит состояние как последовательность событий, а не текущее состояние.

**[[Temporal]]'s implementation / Реализация в [[Temporal]]:**
```
Event History:
1. WorkflowStarted
2. ActivityScheduled(charge_card)
3. ActivityCompleted(charge_card, success)
4. TimerStarted(7 days)
5. TimerFired
6. ...
```

**Benefits / Преимущества:**
- Full audit trail
- Replay for recovery
- Debugging (see exact execution path)
- No lost state on crashes

---

### Q5: What are History Shards in [[Temporal]]?
**Что такое History Shards в [[Temporal]]?**

**Answer / Ответ:**

History Shards are the fundamental scalability unit in [[Temporal]]. Each workflow is assigned to exactly one shard based on hash(workflowId) % numShards.

History Shards -- это фундаментальная единица масштабируемости в [[Temporal]]. Каждый workflow привязывается к одному шарду на основе hash(workflowId) % numShards.

**Key points / Ключевые моменты:**
- Each shard has exactly one owner (History Service instance)
- Shards are redistributed on node failure
- Default: 512 shards, max ~50k tasks/second
- Cannot change shard count without cluster recreation

---

### Q6: Why must [[Temporal]] workflow code be deterministic?
**Почему код workflow в [[Temporal]] должен быть детерминированным?**

**Answer / Ответ:**

[[Temporal]] replays workflow code from the beginning using event history to reconstruct state. Non-deterministic code produces different results on replay, causing corruption.

[[Temporal]] воспроизводит код workflow с начала, используя историю событий для восстановления состояния. Недетерминированный код даёт разные результаты при воспроизведении, вызывая повреждение данных.

**Forbidden in workflow / Запрещено в workflow:**
```python
random.random()      -> Use workflow.random()
datetime.now()       -> Use workflow.now()
requests.get()       -> Use Activity
time.sleep()         -> Use workflow.sleep()
Global mutable state -> Use local variables
```

---

### Q7: What's the difference between a Workflow and an Activity in [[Temporal]]?
**В чём разница между Workflow и Activity в [[Temporal]]?**

**Answer / Ответ:**

| Workflow | Activity |
|----------|----------|
| Orchestration logic | Actual work (side effects) |
| Must be deterministic | Can be non-deterministic |
| Replayed on recovery | Re-executed on failure |
| Lightweight | Can be resource-intensive |
| Can wait for days | Should complete quickly |

**Example / Пример:**
```python
# Workflow (orchestration)
async def process_order():
    await charge_card_activity()      # Activity
    await workflow.sleep(days=7)      # Durable timer
    await send_review_request()       # Activity

# Activity (actual work)
async def charge_card_activity():
    response = stripe.charge(...)     # External call OK
    return response
```

---

## Category 3: [[Airflow]]

### Q8: What was the main limitation of [[Airflow]] 1.x scheduler?
**Какое было основное ограничение scheduler в [[Airflow]] 1.x?**

**Answer / Ответ:**

**Single Point of Failure (SPOF)** -- only one scheduler could run at a time. If it died, no tasks were scheduled until manual restart.

**Единая точка отказа (SPOF)** -- мог работать только один scheduler. При его падении задачи не планировались до ручного перезапуска.

**[[Airflow]] 2.x solution / Решение в [[Airflow]] 2.x:**
- Multiple schedulers with row-level locking
- `SELECT ... FOR UPDATE SKIP LOCKED`
- Each scheduler locks and processes different tasks
- Automatic failover (no manual intervention)

---

### Q9: What is XCom in [[Airflow]] and what are its limitations?
**Что такое XCom в [[Airflow]] и какие у него ограничения?**

**Answer / Ответ:**

**XCom (Cross-Communication)** -- mechanism for passing small amounts of data between tasks.

**XCom (Cross-Communication)** -- механизм передачи небольших объёмов данных между задачами.

**Limitations / Ограничения:**
- Stored in metadata database
- Size limit: ~48KB (MySQL), ~1GB (PostgreSQL)
- Serialization overhead
- Not for large datasets

**Best practice / Best practice:**
Pass file paths (S3/GCS URLs) instead of actual data.

---

### Q10: Explain the difference between execution_date and actual run time in [[Airflow]].
**Объясните разницу между execution_date и фактическим временем запуска в [[Airflow]].**

**Answer / Ответ:**

```
DAG: schedule='@daily', start_date='Jan 1'

Timeline:
Jan 1         Jan 2         Jan 3
├─────────────├─────────────├─────────────
              ↑             ↑
         Run for Jan 1   Run for Jan 2
         exec_date=Jan 1 exec_date=Jan 2
```

`execution_date` = start of data interval being processed
Actual run time = end of interval

**Why / Зачем:**
"Process yesterday's data" pattern. Run at midnight processes previous day.

---

### Q11: What Executor types are available in [[Airflow]]?
**Какие типы Executor доступны в [[Airflow]]?**

**Answer / Ответ:**

| Executor | Use Case | Pros | Cons |
|----------|----------|------|------|
| LocalExecutor | Development | Simple, no deps | Single machine |
| CeleryExecutor | Production (static) | Distributed, fast | Requires broker |
| KubernetesExecutor | Cloud-native | Dynamic scaling | Pod startup latency |
| CeleryKubernetes | Hybrid | Best of both | Complex setup |

---

## Category 4: [[Conductor]]

### Q12: How does Netflix [[Conductor]] differ from [[Temporal]]?
**Чем Netflix [[Conductor]] отличается от [[Temporal]]?**

**Answer / Ответ:**

| Aspect | [[Conductor]] | [[Temporal]] |
|--------|-----------|----------|
| Workflow definition | JSON (declarative) | Code (imperative) |
| Worker communication | REST API polling | gRPC + SDK |
| State model | Task status tracking | Event Sourcing |
| Replay | No automatic replay | Full deterministic replay |
| Language support | Any (REST) | SDK required |

**Choose [[Conductor]] when / Выбирайте [[Conductor]] когда:**
- Prefer JSON over code
- Need language-agnostic workers
- Visual debugging is critical

---

### Q13: What task types does [[Conductor]] support?
**Какие типы задач поддерживает [[Conductor]]?**

**Answer / Ответ:**

- **SIMPLE** -- Worker executes task
- **FORK_JOIN** -- Parallel branches
- **DECISION** -- Conditional branching (switch/case)
- **DYNAMIC** -- Task type determined at runtime
- **SUB_WORKFLOW** -- Invoke another workflow
- **HTTP** -- Built-in HTTP call (no worker)
- **WAIT** -- Wait for signal/timeout

---

## Category 5: System Design / Проектирование систем

### Q14: How would you design a highly available orchestrator?
**Как бы вы спроектировали высокодоступный оркестратор?**

**Answer / Ответ:**

**Two main approaches / Два основных подхода:**

**1. Leader Election (Active-Standby):**
```
┌──────────┐    ┌──────────┐
│  Leader  │    │ Standby  │
│ (active) │    │ (idle)   │
└──────────┘    └──────────┘
     │               │
     ▼               │
  Process        Wait for
  commands       leader fail
```
- Simpler implementation
- Resource waste (standby idle)
- Failover delay (~10 seconds)

**2. Partitioned Load Distribution (Active-Active):**
```
┌──────────┐    ┌──────────┐
│ Instance │    │ Instance │
│   (P0-3) │    │   (P4-7) │
└──────────┘    └──────────┘
     │               │
     ▼               ▼
  Process        Process
  partitions     partitions
  0,1,2,3        4,5,6,7
```
- Better resource utilization
- Linear scalability
- More complex (rebalancing)

**Recommendation:** Partitioned approach ([[Temporal]]/[[Kafka]] pattern)

---

### Q15: How do you handle [[Idempotency]] in workflow orchestration?
**Как обеспечить идемпотентность в оркестрации workflow?**

**Answer / Ответ:**

**Problem:** Duplicate messages during rebalancing or retries.

**Solution patterns / Паттерны решения:**

**1. SETNX-based deduplication:**
```python
async def handle_command(job_id):
    key = f"processed:{job_id}"
    if await redis.setnx(key, "1"):
        await redis.expire(key, 86400 * 7)  # 7 days TTL
        await process_job(job_id)
    else:
        logger.info(f"Duplicate: {job_id}")
```

**2. Database unique constraint:**
```sql
INSERT INTO job_executions (job_id, ...)
ON CONFLICT (job_id) DO NOTHING;
```

**3. Idempotency key in request:**
```python
@task(idempotency_key=lambda args: args['order_id'])
def process_order(order_id):
    ...
```

---

### Q16: How would you handle workflow versioning?
**Как бы вы обрабатывали версионирование workflow?**

**Answer / Ответ:**

**Challenge:** Running workflows use old code, new workflows need new code.

**Strategies / Стратегии:**

**1. [[Temporal]]: Workflow Versioning API**
```python
version = workflow.get_version("feature-x", 1, 2)
if version == 1:
    await old_logic()
else:
    await new_logic()
```

**2. [[Airflow]]: DAG Versioning**
```python
# v1 continues running
dag_id = 'pipeline_v1'

# Deploy v2 separately
dag_id = 'pipeline_v2'
```

**3. [[Conductor]]: Workflow Definition Versions**
```json
{
  "name": "video_processing",
  "version": 2,
  ...
}
```

---

### Q17: How do you monitor workflow health?
**Как мониторить состояние workflow?**

**Answer / Ответ:**

**Key metrics to track / Ключевые метрики:**

| Category | Metrics |
|----------|---------|
| **Throughput** | Workflows started/completed per second |
| **Latency** | Schedule-to-start, execution time |
| **Errors** | Failed workflows, failed activities |
| **Queue** | Pending tasks, queue depth |
| **Resources** | Worker utilization, DB connections |

**Alerting rules / Правила алертинга:**
- Workflow failure rate > 5%
- Average latency > 2x baseline
- Queue depth growing for 15 minutes
- Worker pool saturation > 90%

---

## Category 6: [[Polyvision]]-Specific / Специфичные для Polyvision

### Q18: Why did [[Polyvision]] choose custom orchestration over [[Temporal]]?
**Почему [[Polyvision]] выбрал custom оркестрацию вместо [[Temporal]]?**

**Answer / Ответ:**

**Decision rationale / Обоснование решения:**

1. **Linear pipeline, not complex branching**
   - Upload -> Stitch -> Detect -> Track -> VCam -> Encode
   - No complex business logic requiring [[Temporal]]'s power

2. **Existing Celery infrastructure**
   - Team has Celery expertise
   - Redis already deployed for caching

3. **Operational simplicity**
   - [[Temporal]] adds significant operational complexity
   - History Service, Matching Service, SDK learning curve

4. **Partitioned HA with [[Redpanda]]**
   - Adopted [[Temporal]]'s pattern (partitioned processing)
   - Without full [[Temporal]] infrastructure

**Trade-offs accepted / Принятые компромиссы:**
- Manual state management (vs automatic in [[Temporal]])
- No automatic replay (manual retry logic)
- Less sophisticated debugging tools

---

### Q19: How does [[Polyvision]] handle orchestrator high availability?
**Как [[Polyvision]] обеспечивает высокую доступность оркестратора?**

**Answer / Ответ:**

**Architecture / Архитектура:**
```
Orchestrator replicas (2+) consume from Redpanda partitions

┌─────────────────────────────────────────────────────────────────┐
│  Redpanda: polyvision.jobs.commands (8 partitions)              │
│  ┌─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┐            │
│  │ P0  │ P1  │ P2  │ P3  │ P4  │ P5  │ P6  │ P7  │            │
│  └──┬──┴──┬──┴─────┴─────┴──┬──┴──┬──┴─────┴─────┘            │
│     │     │                 │     │                             │
│     ▼     ▼                 ▼     ▼                             │
│  ┌─────────────┐        ┌─────────────┐                        │
│  │Orchestrator │        │Orchestrator │                        │
│  │  Replica 1  │        │  Replica 2  │                        │
│  │  (P0-P3)    │        │  (P4-P7)    │                        │
│  └─────────────┘        └─────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
```

**Failover / Отказоустойчивость:**
- Replica 1 dies -> [[Redpanda]] reassigns P0-P3 to Replica 2
- [[Idempotency]] via Redis SETNX prevents duplicate processing
- ~10 second failover time

---

### Q20: Explain [[Polyvision]]'s partition key strategy.
**Объясните стратегию partition key в [[Polyvision]].**

**Answer / Ответ:**

**Partition key format:**
```
{organization_id}:{match_id}
```

**Benefits / Преимущества:**

1. **Ordering guarantee:** All events for a match go to same partition -> processed in order
2. **Load distribution:** Different matches spread across partitions
3. **Tenant isolation:** Organization-level grouping for potential future sharding

**Example / Пример:**
```
org-1:match-100 → hash → Partition 3
org-1:match-101 → hash → Partition 7
org-2:match-200 → hash → Partition 1
```

---

## Category 7: Advanced / Продвинутые вопросы

### Q21: How would you implement long-running timers without [[Temporal]]?
**Как бы вы реализовали долгие таймеры без [[Temporal]]?**

**Answer / Ответ:**

**Options / Варианты:**

**1. Database-based timers:**
```python
# Store timer in DB
INSERT INTO scheduled_tasks (execute_at, payload)
VALUES ('2024-01-15 00:00:00', '{"job_id": "123"}');

# Poller checks every minute
SELECT * FROM scheduled_tasks
WHERE execute_at <= NOW()
FOR UPDATE SKIP LOCKED;
```

**2. Redis sorted sets:**
```python
# Schedule
redis.zadd('timers', {job_id: execute_timestamp})

# Poll
due_tasks = redis.zrangebyscore('timers', 0, time.time())
```

**3. External scheduler (Celery beat):**
```python
@celery.task
def check_review_requests():
    # Query jobs ready for review request
    ...

CELERYBEAT_SCHEDULE = {
    'check-reviews': {
        'task': 'check_review_requests',
        'schedule': crontab(minute='*/5'),
    }
}
```

---

### Q22: How do you handle partial failures in multi-step workflows?
**Как обрабатывать частичные отказы в многошаговых workflow?**

**Answer / Ответ:**

**Saga Pattern / Паттерн Saga:**

```
Forward:  T1 → T2 → T3 → T4 → T5
                          ↓ (T4 fails)
Compensate: C3 ← C2 ← C1 ← (rollback)
```

**Implementation / Реализация:**

```python
class OrderSaga:
    def execute(self):
        try:
            self.reserve_inventory()
            self.charge_payment()
            self.ship_order()
        except PaymentError:
            self.compensate_inventory()
            raise
        except ShippingError:
            self.compensate_payment()
            self.compensate_inventory()
            raise

    def compensate_inventory(self):
        # Release reserved inventory
        pass

    def compensate_payment(self):
        # Refund payment
        pass
```

**Key points / Ключевые моменты:**
- Each step must have a compensating action
- Compensations must be idempotent
- Log all steps for debugging

---

### Q23: Compare polling vs push-based task delivery.
**Сравните polling и push-based доставку задач.**

**Answer / Ответ:**

| Aspect | Polling | Push (WebSocket/gRPC stream) |
|--------|---------|------------------------------|
| **Latency** | Depends on interval | Near real-time |
| **Load** | Constant requests | Only when tasks exist |
| **Scaling** | Simple | Need sticky sessions |
| **Worker crash** | Task returns to queue | Need heartbeat |
| **Firewall** | Easy (outbound HTTP) | May need config |

**Used by / Используется:**
- Polling: [[Conductor]], Celery
- Push/Streaming: [[Temporal]] (long poll with streaming)

---

### Q24: How would you test workflow orchestration?
**Как бы вы тестировали оркестрацию workflow?**

**Answer / Ответ:**

**Testing layers / Уровни тестирования:**

**1. Unit tests (workflow logic):**
```python
# Temporal: Workflow testing framework
async def test_order_workflow():
    async with WorkflowEnvironment() as env:
        result = await env.client.execute_workflow(
            OrderWorkflow.run,
            args=["order-123"],
            task_queue="test",
        )
        assert result.status == "completed"
```

**2. Integration tests (with real services):**
```python
# Test with actual Celery worker
@pytest.fixture
def celery_worker(celery_app):
    yield start_worker(celery_app)

def test_pipeline_integration(celery_worker):
    result = process_job.delay(job_id="test-123")
    assert result.get(timeout=30) == "success"
```

**3. Chaos testing:**
- Kill workers mid-execution
- Simulate network partitions
- Test [[Idempotency]] with duplicate messages

---

### Q25: Design a workflow system from scratch. What components would you need?
**Спроектируйте систему workflow с нуля. Какие компоненты нужны?**

**Answer / Ответ:**

**Minimal components / Минимальные компоненты:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    WORKFLOW SYSTEM COMPONENTS                    │
│                                                                  │
│  1. WORKFLOW DEFINITION STORE                                   │
│     • Store workflow templates (JSON/code)                      │
│     • Version management                                         │
│                                                                  │
│  2. EXECUTION ENGINE                                            │
│     • Parse workflow definition                                  │
│     • Determine next tasks                                       │
│     • Handle branching/joining                                   │
│                                                                  │
│  3. STATE STORE                                                 │
│     • Current workflow state                                     │
│     • Task results                                               │
│     • Event history (for replay)                                 │
│                                                                  │
│  4. TASK QUEUE                                                  │
│     • Distribute tasks to workers                                │
│     • Handle priorities                                          │
│     • Support partitioning for scale                            │
│                                                                  │
│  5. WORKER FRAMEWORK                                            │
│     • Task execution                                             │
│     • Heartbeat/health checks                                    │
│     • Result reporting                                           │
│                                                                  │
│  6. SCHEDULER                                                   │
│     • Cron-based triggers                                        │
│     • Timer management                                           │
│                                                                  │
│  7. API/UI                                                      │
│     • Start/stop workflows                                       │
│     • Monitor progress                                           │
│     • Debug failures                                             │
│                                                                  │
│  8. OBSERVABILITY                                               │
│     • Metrics (latency, throughput, errors)                     │
│     • Distributed tracing                                        │
│     • Alerting                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Production considerations / Соображения для production:**
- High availability for each component
- Horizontal scalability
- Disaster recovery / backups
- Multi-tenancy / isolation

---

## Quick Reference Card / Краткая справочная карточка

```
┌─────────────────────────────────────────────────────────────────┐
│  ORCHESTRATION CHEAT SHEET                                      │
│                                                                  │
│  Task-centric (Airflow):    Data-centric (Temporal):           │
│  • DAG-based                • Event Sourcing                    │
│  • Scheduled execution      • Event-driven                      │
│  • ETL pipelines            • Business workflows                │
│                                                                  │
│  Orchestration:             Choreography:                       │
│  • Central control          • Event reactions                   │
│  • Easy debugging           • Loose coupling                    │
│  • Complex logic OK         • 2-3 services max                  │
│                                                                  │
│  HA Patterns:                                                   │
│  • Leader Election: Simple, resource waste                      │
│  • Partitioned: Scalable, complex                               │
│                                                                  │
│  Idempotency:                                                   │
│  • SETNX + TTL                                                  │
│  • DB unique constraint                                         │
│  • Idempotency key in request                                   │
│                                                                  │
│  Key Metrics:                                                   │
│  • Schedule-to-start latency                                    │
│  • Failure rate                                                 │
│  • Queue depth                                                  │
│  • Worker utilization                                           │
└─────────────────────────────────────────────────────────────────┘
```

## Связано с
- [[Orchestration]]
- [[Temporal]]
- [[Conductor]]
- [[Airflow]]

## Ресурсы
- [[Orchestration]] -- overview note
- [[PV-Orchestration]] -- Polyvision decision

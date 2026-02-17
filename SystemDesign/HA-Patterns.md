---
tags:
  - system-design
  - high-availability
  - ha
created: 2026-02-17
---

# High Availability Patterns / Паттерны высокой доступности

> **Reading time:** ~18 min | **Время чтения:** ~18 мин

## Что это

Паттерны обеспечения высокой доступности (HA) в распределённых системах: Active-Passive, Active-Active, N+1 Redundancy, Leader Election, Split-Brain, Health Checks, Deployment Patterns.

**High Availability (HA)** is the ability of a system to remain operational and accessible for a high percentage of time, minimizing downtime.

**Высокая доступность (HA)** — это способность системы оставаться работоспособной и доступной в течение высокого процента времени, минимизируя простои.

---

## Availability Metrics / Метрики доступности

```
┌─────────────────────────────────────────────────────────────────────┐
│  AVAILABILITY LEVELS (The "Nines")                                  │
│                                                                      │
│  Availability │ Downtime/Year │ Downtime/Month │ Downtime/Week     │
│  ─────────────┼───────────────┼────────────────┼─────────────────   │
│  99%          │ 3.65 days     │ 7.31 hours     │ 1.68 hours        │
│  99.9%        │ 8.77 hours    │ 43.83 min      │ 10.08 min         │
│  99.95%       │ 4.38 hours    │ 21.92 min      │ 5.04 min          │
│  99.99%       │ 52.60 min     │ 4.38 min       │ 1.01 min          │
│  99.999%      │ 5.26 min      │ 26.30 sec      │ 6.05 sec          │
│                                                                      │
│  Availability = (Total Time - Downtime) / Total Time × 100%        │
│                                                                      │
│  Example:                                                           │
│  SLO: 99.9% availability                                            │
│  Month: 30 days × 24 hours × 60 min = 43,200 minutes               │
│  Allowed downtime: 43,200 × 0.001 = 43.2 minutes                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Core HA Patterns / Основные паттерны HA

### 1. Active-Passive (Standby) / Активный-Пассивный

```
┌─────────────────────────────────────────────────────────────────────┐
│  ACTIVE-PASSIVE PATTERN                                             │
│                                                                      │
│  Normal Operation:                                                  │
│  ┌──────────────┐                    ┌──────────────┐              │
│  │   ACTIVE     │                    │   PASSIVE    │              │
│  │  (Primary)   │                    │  (Standby)   │              │
│  │              │◀─── Heartbeat ────▶│              │              │
│  │  ┌────────┐  │    (health check)  │  ┌────────┐  │              │
│  │  │  App   │  │                    │  │  App   │  │              │
│  │  │ Server │  │                    │  │ Server │  │              │
│  │  └────────┘  │                    │  │ (idle) │  │              │
│  └──────┬───────┘                    │  └────────┘  │              │
│         │                            └──────────────┘              │
│         │ All traffic                                               │
│         ▼                                                           │
│  ┌──────────────┐                                                  │
│  │   Clients    │                                                  │
│  └──────────────┘                                                  │
│                                                                      │
│  Failover:                                                          │
│  ┌──────────────┐                    ┌──────────────┐              │
│  │   ACTIVE     │     Failure!       │   PASSIVE    │              │
│  │  (Primary)   │        ✗           │  (Standby)   │              │
│  │              │                    │      ↓       │              │
│  │      ✗       │                    │  PROMOTED    │              │
│  │              │                    │  TO ACTIVE   │              │
│  └──────────────┘                    └──────┬───────┘              │
│                                             │                       │
│                                             │ Traffic redirected    │
│                                             ▼                       │
│                                      ┌──────────────┐              │
│                                      │   Clients    │              │
│                                      └──────────────┘              │
│                                                                      │
│  Pros:                              Cons:                           │
│  ✓ Simple to implement             ✗ Standby resources wasted      │
│  ✓ Clear failover logic            ✗ Failover delay (seconds-min)  │
│  ✓ No split-brain risk             ✗ Not true HA during failover   │
│  ✓ Easy data consistency           ✗ Manual recovery often needed  │
└─────────────────────────────────────────────────────────────────────┘
```

**Use cases / Сценарии использования:**
- Databases with synchronous replication
- Legacy applications not designed for clustering
- Systems where simplicity is valued over efficiency

---

### 2. Active-Active / Активный-Активный

```
┌─────────────────────────────────────────────────────────────────────┐
│  ACTIVE-ACTIVE PATTERN                                              │
│                                                                      │
│  Normal Operation:                                                  │
│                    ┌─────────────────┐                             │
│                    │  Load Balancer  │                             │
│                    └────────┬────────┘                             │
│                             │                                       │
│              ┌──────────────┼──────────────┐                       │
│              │              │              │                       │
│              ▼              ▼              ▼                       │
│       ┌──────────┐   ┌──────────┐   ┌──────────┐                  │
│       │ ACTIVE   │   │ ACTIVE   │   │ ACTIVE   │                  │
│       │ Node 1   │   │ Node 2   │   │ Node 3   │                  │
│       │  33%     │   │  33%     │   │  33%     │                  │
│       │ traffic  │   │ traffic  │   │ traffic  │                  │
│       └──────────┘   └──────────┘   └──────────┘                  │
│                                                                      │
│  Node Failure:                                                      │
│                    ┌─────────────────┐                             │
│                    │  Load Balancer  │                             │
│                    └────────┬────────┘                             │
│                             │                                       │
│              ┌──────────────┼──────────────┐                       │
│              │              │              │                       │
│              ▼              ▼              ▼                       │
│       ┌──────────┐   ┌──────────┐   ┌──────────┐                  │
│       │ ACTIVE   │   │  FAILED  │   │ ACTIVE   │                  │
│       │ Node 1   │   │    ✗     │   │ Node 3   │                  │
│       │  50%     │   │ (removed │   │  50%     │                  │
│       │ traffic  │   │  from LB)│   │ traffic  │                  │
│       └──────────┘   └──────────┘   └──────────┘                  │
│                                                                      │
│  Pros:                              Cons:                           │
│  ✓ Full resource utilization       ✗ Complex state management      │
│  ✓ Instant failover (LB removes)   ✗ Data consistency challenges   │
│  ✓ Linear scalability              ✗ Split-brain risk             │
│  ✓ No wasted standby capacity      ✗ More complex deployments      │
└─────────────────────────────────────────────────────────────────────┘
```

**Use cases / Сценарии использования:**
- Stateless services (API servers, web servers)
- Services with shared external state (database, cache)
- High-traffic applications requiring horizontal scaling

---

### 3. N+1 Redundancy / N+1 резервирование

```
┌─────────────────────────────────────────────────────────────────────┐
│  N+1 REDUNDANCY                                                     │
│                                                                      │
│  Definition: N nodes handle normal load, +1 node for redundancy    │
│                                                                      │
│  Example: 3+1 configuration (N=3)                                   │
│                                                                      │
│  Normal:                                                            │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                              │
│  │ Node │ │ Node │ │ Node │ │ Spare│                              │
│  │  1   │ │  2   │ │  3   │ │  4   │                              │
│  │ 33%  │ │ 33%  │ │ 33%  │ │  0%  │                              │
│  └──────┘ └──────┘ └──────┘ └──────┘                              │
│                                                                      │
│  Node 2 fails:                                                      │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                              │
│  │ Node │ │ FAIL │ │ Node │ │ Node │                              │
│  │  1   │ │  ✗   │ │  3   │ │  4   │                              │
│  │ 33%  │ │      │ │ 33%  │ │ 33%  │ ← Takes over                 │
│  └──────┘ └──────┘ └──────┘ └──────┘                              │
│                                                                      │
│  Variants:                                                          │
│  • N+1: One spare for N active nodes                               │
│  • N+2: Two spares (higher redundancy)                             │
│  • 2N: Full duplication (100% redundancy)                          │
│                                                                      │
│  Cost efficiency: 25% overhead for 3+1 vs 100% for Active-Passive  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Leader Election / Выбор лидера

### Why Leader Election? / Зачем выбор лидера?

Leader election is needed when:
- Only one node should perform a task (avoid duplicates)
- Coordination required (distributed locks)
- Single writer pattern (databases)

### Common Approaches / Распространённые подходы

```
┌─────────────────────────────────────────────────────────────────────┐
│  LEADER ELECTION MECHANISMS                                         │
│                                                                      │
│  1. CONSENSUS-BASED (Raft, Paxos, ZAB)                             │
│     ┌─────────────────────────────────────────────────────────┐    │
│     │  Nodes vote to elect leader with majority agreement      │    │
│     │  Examples: etcd, Consul, ZooKeeper                       │    │
│     │  Pros: Strong consistency, battle-tested                 │    │
│     │  Cons: Operational complexity, network partitions        │    │
│     └─────────────────────────────────────────────────────────┘    │
│                                                                      │
│  2. DISTRIBUTED LOCK (Redis, etcd)                                 │
│     ┌─────────────────────────────────────────────────────────┐    │
│     │  First node to acquire lock becomes leader               │    │
│     │  Lock has TTL, requires renewal                          │    │
│     │  Pros: Simple to implement                               │    │
│     │  Cons: Lock expiry edge cases, clock skew issues         │    │
│     └─────────────────────────────────────────────────────────┘    │
│                                                                      │
│  3. CONSUMER GROUP REBALANCING (Kafka/Redpanda)                    │
│     ┌─────────────────────────────────────────────────────────┐    │
│     │  Broker assigns partitions; first consumer = coordinator │    │
│     │  Pros: No separate coordination system                   │    │
│     │  Cons: Tied to message broker                            │    │
│     └─────────────────────────────────────────────────────────┘    │
│                                                                      │
│  4. DATABASE-BASED (PostgreSQL advisory locks)                     │
│     ┌─────────────────────────────────────────────────────────┐    │
│     │  SELECT pg_try_advisory_lock(12345);                     │    │
│     │  Pros: Use existing database                             │    │
│     │  Cons: Database becomes SPOF                             │    │
│     └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### Leader Election with Redis / Выбор лидера через Redis

```python
import redis
import time
import uuid

class RedisLeaderElection:
    def __init__(self, redis_client, lock_name, ttl_seconds=30):
        self.redis = redis_client
        self.lock_name = lock_name
        self.ttl = ttl_seconds
        self.node_id = str(uuid.uuid4())
        self._is_leader = False

    def try_become_leader(self) -> bool:
        """Attempt to become leader using SETNX."""
        # SETNX + EXPIRE atomically (SET with NX and EX)
        acquired = self.redis.set(
            self.lock_name,
            self.node_id,
            nx=True,  # Only set if not exists
            ex=self.ttl  # Expiry in seconds
        )
        self._is_leader = acquired
        return acquired

    def renew_leadership(self) -> bool:
        """Renew lock if we're still the leader."""
        # Only renew if we hold the lock
        current = self.redis.get(self.lock_name)
        if current and current.decode() == self.node_id:
            self.redis.expire(self.lock_name, self.ttl)
            return True
        self._is_leader = False
        return False

    def release_leadership(self):
        """Release leadership gracefully."""
        # Only delete if we hold the lock (Lua script for atomicity)
        script = """
        if redis.call('get', KEYS[1]) == ARGV[1] then
            return redis.call('del', KEYS[1])
        else
            return 0
        end
        """
        self.redis.eval(script, 1, self.lock_name, self.node_id)
        self._is_leader = False

    def is_leader(self) -> bool:
        return self._is_leader


# Usage
leader_election = RedisLeaderElection(redis.Redis(), 'orchestrator:leader')

while True:
    if leader_election.is_leader():
        if leader_election.renew_leadership():
            do_leader_work()
        else:
            # Lost leadership
            handle_demotion()
    else:
        if leader_election.try_become_leader():
            handle_promotion()
        else:
            do_follower_work()

    time.sleep(5)  # Check interval
```

---

## Split-Brain Problem / Проблема Split-Brain

### What is Split-Brain? / Что такое Split-Brain?

```
┌─────────────────────────────────────────────────────────────────────┐
│  SPLIT-BRAIN SCENARIO                                               │
│                                                                      │
│  Normal state:                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Node A (Leader) ←─────────────→ Node B (Follower)          │   │
│  │        ↑                              ↑                      │   │
│  │        │         Network OK           │                      │   │
│  │        └──────────────────────────────┘                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Network partition:                                                 │
│  ┌───────────────────┐    ║    ┌───────────────────┐              │
│  │  Node A           │    ║    │  Node B           │              │
│  │  (thinks: Leader) │    ║    │  (thinks: Leader) │              │
│  │        ↑          │    ║    │        ↑          │              │
│  │        │          │    ║    │        │          │              │
│  │    Clients 1-5    │    ║    │    Clients 6-10   │              │
│  └───────────────────┘    ║    └───────────────────┘              │
│                         PARTITION                                   │
│                                                                      │
│  Both nodes accept writes → DATA INCONSISTENCY!                    │
│  Client 1 writes order-1 to Node A                                 │
│  Client 6 writes order-1 to Node B (different data!)               │
└─────────────────────────────────────────────────────────────────────┘
```

### Solutions / Решения

```
┌─────────────────────────────────────────────────────────────────────┐
│  SPLIT-BRAIN PREVENTION                                             │
│                                                                      │
│  1. QUORUM-BASED DECISIONS                                          │
│     Need majority (N/2 + 1) to operate                             │
│     3 nodes: need 2 to agree                                        │
│     5 nodes: need 3 to agree                                        │
│     Minority partition becomes read-only                           │
│                                                                      │
│  2. FENCING (STONITH - Shoot The Other Node In The Head)          │
│     When becoming leader, "fence off" old leader                   │
│     Methods: Power off, revoke storage access                      │
│     Ensures old leader cannot make changes                         │
│                                                                      │
│  3. FENCING TOKENS                                                  │
│     Each leader gets monotonically increasing token                │
│     Storage rejects writes with lower token                        │
│     Even if old leader runs, writes rejected                       │
│                                                                      │
│  4. LEASE-BASED LEADERSHIP                                          │
│     Leader has time-limited lease                                   │
│     Must renew before expiry to remain leader                      │
│     Old leader automatically demotes when lease expires            │
│     Requires synchronized clocks!                                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Health Checks and Monitoring / Проверки здоровья и мониторинг

### Health Check Types / Типы проверок здоровья

```
┌─────────────────────────────────────────────────────────────────────┐
│  HEALTH CHECK TYPES                                                 │
│                                                                      │
│  1. LIVENESS PROBE                                                  │
│     "Is the process running?"                                       │
│     Action: Restart container if unhealthy                         │
│     Example: TCP connect, HTTP /health returns 200                 │
│                                                                      │
│  2. READINESS PROBE                                                 │
│     "Can it serve traffic?"                                         │
│     Action: Remove from load balancer if unhealthy                 │
│     Example: /ready checks DB connection, cache warmup             │
│                                                                      │
│  3. STARTUP PROBE                                                   │
│     "Has it finished initializing?"                                 │
│     Action: Don't check liveness until startup completes           │
│     Example: Slow-starting apps (loading models, warming caches)   │
│                                                                      │
│  Best practices:                                                    │
│  • Liveness: Simple check (is process responding?)                 │
│  • Readiness: Check dependencies (DB, cache, required services)    │
│  • Separate endpoints: /health vs /ready                           │
│  • Don't check everything in liveness (causes restart cascades)    │
└─────────────────────────────────────────────────────────────────────┘
```

### Kubernetes Example / Пример для Kubernetes

```yaml
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: app
    livenessProbe:
      httpGet:
        path: /health
        port: 8080
      initialDelaySeconds: 10
      periodSeconds: 5
      failureThreshold: 3

    readinessProbe:
      httpGet:
        path: /ready
        port: 8080
      initialDelaySeconds: 5
      periodSeconds: 5
      failureThreshold: 2

    startupProbe:
      httpGet:
        path: /health
        port: 8080
      failureThreshold: 30
      periodSeconds: 10
```

---

## Deployment Patterns for HA / Паттерны развёртывания для HA

### Blue-Green Deployment

```
┌─────────────────────────────────────────────────────────────────────┐
│  BLUE-GREEN DEPLOYMENT                                              │
│                                                                      │
│  Step 1: Blue is live                                               │
│  ┌─────────────────┐           ┌─────────────────┐                 │
│  │  BLUE (v1.0)    │◀──────────│  Load Balancer  │                 │
│  │  Active         │    100%   │                 │                 │
│  └─────────────────┘           └─────────────────┘                 │
│  ┌─────────────────┐                                               │
│  │  GREEN (empty)  │                                               │
│  │  Idle           │                                               │
│  └─────────────────┘                                               │
│                                                                      │
│  Step 2: Deploy to Green                                            │
│  ┌─────────────────┐           ┌─────────────────┐                 │
│  │  BLUE (v1.0)    │◀──────────│  Load Balancer  │                 │
│  │  Active         │    100%   │                 │                 │
│  └─────────────────┘           └─────────────────┘                 │
│  ┌─────────────────┐                                               │
│  │  GREEN (v2.0)   │ ← Deploy new version here                    │
│  │  Testing        │                                               │
│  └─────────────────┘                                               │
│                                                                      │
│  Step 3: Switch traffic                                             │
│  ┌─────────────────┐           ┌─────────────────┐                 │
│  │  BLUE (v1.0)    │           │  Load Balancer  │                 │
│  │  Standby        │           │                 │                 │
│  └─────────────────┘           └────────┬────────┘                 │
│  ┌─────────────────┐                    │                          │
│  │  GREEN (v2.0)   │◀───────────────────┘                          │
│  │  Active         │    100%                                        │
│  └─────────────────┘                                               │
│                                                                      │
│  Rollback: Switch back to Blue (instant)                           │
└─────────────────────────────────────────────────────────────────────┘
```

### Canary Deployment

```
┌─────────────────────────────────────────────────────────────────────┐
│  CANARY DEPLOYMENT                                                  │
│                                                                      │
│  Gradual traffic shift:                                             │
│                                                                      │
│  Phase 1: 5% to canary                                              │
│  ┌─────────────────┐  95%                                          │
│  │  Stable (v1.0)  │◀───────────┐                                  │
│  └─────────────────┘            │   ┌─────────────────┐            │
│  ┌─────────────────┐            ├───│  Load Balancer  │            │
│  │  Canary (v2.0)  │◀───────────┘   │                 │            │
│  └─────────────────┘   5%           └─────────────────┘            │
│                                                                      │
│  Phase 2: 25% if metrics OK                                        │
│  ┌─────────────────┐  75%                                          │
│  │  Stable (v1.0)  │◀───────────┐                                  │
│  └─────────────────┘            │   ┌─────────────────┐            │
│  ┌─────────────────┐            ├───│  Load Balancer  │            │
│  │  Canary (v2.0)  │◀───────────┘   │                 │            │
│  └─────────────────┘  25%           └─────────────────┘            │
│                                                                      │
│  Phase 3: 100% (promote)                                            │
│  ┌─────────────────┐                                               │
│  │  Stable (v2.0)  │◀────────────── Full traffic                   │
│  └─────────────────┘                                               │
│                                                                      │
│  Metrics to watch:                                                  │
│  • Error rate (should not increase)                                │
│  • Latency (p50, p95, p99)                                         │
│  • Business metrics (conversion, etc.)                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## HA Anti-Patterns / Антипаттерны HA

```
┌─────────────────────────────────────────────────────────────────────┐
│  COMMON HA MISTAKES                                                 │
│                                                                      │
│  1. SINGLE POINT OF FAILURE IN "HA" DESIGN                         │
│     • "HA" app but single database                                 │
│     • HA database but single load balancer                         │
│     • Everything HA but single DNS provider                        │
│                                                                      │
│  2. CORRELATED FAILURES                                             │
│     • All replicas in same availability zone                       │
│     • All replicas on same physical host                           │
│     • Shared dependency that can fail                              │
│                                                                      │
│  3. IGNORING GRACEFUL DEGRADATION                                   │
│     • System completely fails if one component fails               │
│     • No fallbacks for non-critical features                       │
│                                                                      │
│  4. UNTESTED FAILOVER                                               │
│     • Never tested actual failover process                         │
│     • Failover scripts outdated                                     │
│     • No runbooks for recovery                                     │
│                                                                      │
│  5. CONFIGURATION DRIFT                                             │
│     • Primary and standby have different configs                   │
│     • Standby promoted with wrong settings                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Summary / Итоги

```
┌─────────────────────────────────────────────────────────────────────┐
│  HA PATTERNS SUMMARY                                                │
│                                                                      │
│  Pattern          │ Use When                                        │
│  ─────────────────┼────────────────────────────────────────────────│
│  Active-Passive   │ Simplicity needed, can afford standby cost     │
│  Active-Active    │ Maximum utilization, stateless services        │
│  N+1 Redundancy   │ Balance between cost and redundancy            │
│  Leader Election  │ Single writer needed, coordination required    │
│                                                                      │
│  Key Concepts:                                                      │
│  • Availability measured in "nines" (99.9%, 99.99%, etc.)         │
│  • Split-brain requires quorum or fencing                          │
│  • Health checks: liveness vs readiness                            │
│  • Test failover regularly                                         │
└─────────────────────────────────────────────────────────────────────┘
```

## Связано с

- [[Failover]]
- [[Idempotency]]
- [[Consensus]]
- [[PV-HA]]

## Ресурсы

- [Designing Data-Intensive Applications](https://dataintensive.net/) -- Martin Kleppmann
- [Site Reliability Engineering](https://sre.google/sre-book/table-of-contents/) -- Google
- [AWS Well-Architected Framework - Reliability](https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/)
- [Kubernetes Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)

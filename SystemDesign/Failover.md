---
tags:
  - system-design
  - high-availability
  - failover
created: 2026-02-17
---

# Failover Strategies / Стратегии отказоустойчивости

> **Reading time:** ~15 min | **Время чтения:** ~15 мин

## Что это

Стратегии отказоустойчивости: RTO/RPO, автоматический/ручной/полуавтоматический failover, плавная деградация (Circuit Breaker, Feature Flags), Disaster Recovery (Backup/Restore, Pilot Light, Warm/Hot Standby).

---

## RTO and RPO / RTO и RPO

### Definitions / Определения

```
┌─────────────────────────────────────────────────────────────────────┐
│  RTO AND RPO EXPLAINED                                              │
│                                                                      │
│  Timeline:                                                          │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                      │
│  Last        Disaster    Detection   Recovery    Service            │
│  Backup      Occurs      Complete    Complete    Restored           │
│    │           │            │           │           │               │
│    ▼           ▼            ▼           ▼           ▼               │
│  ──┼───────────┼────────────┼───────────┼───────────┼──────────────│
│    │◀─────────▶│◀──────────────────────▶│                          │
│    │    RPO   │           RTO           │                          │
│    │          │                         │                          │
│                                                                      │
│  RPO (Recovery Point Objective):                                   │
│  • Maximum acceptable data loss (time)                             │
│  • "How much data can we afford to lose?"                          │
│  • Determines backup frequency                                      │
│  • RPO = 1 hour → backup every hour (or less)                      │
│                                                                      │
│  RTO (Recovery Time Objective):                                    │
│  • Maximum acceptable downtime                                      │
│  • "How long until service is restored?"                           │
│  • Determines failover strategy                                     │
│  • RTO = 15 min → need fast failover mechanism                     │
└─────────────────────────────────────────────────────────────────────┘
```

### RTO/RPO Requirements / Требования RTO/RPO

| Tier | RTO | RPO | Example Systems |
|------|-----|-----|-----------------|
| **Mission Critical** | < 1 min | 0 (sync replication) | Payment processing, trading |
| **Business Critical** | < 15 min | < 1 hour | Core business apps, ERP |
| **Standard** | < 4 hours | < 24 hours | Internal tools, reporting |
| **Non-Critical** | < 24 hours | < 1 week | Archive systems, logs |

---

## Failover Types / Типы отказоустойчивости

### 1. Automatic Failover / Автоматическая отказоустойчивость

```
┌─────────────────────────────────────────────────────────────────────┐
│  AUTOMATIC FAILOVER                                                 │
│                                                                      │
│  ┌─────────────┐         ┌─────────────┐         ┌─────────────┐  │
│  │   Primary   │         │  Watchdog   │         │   Standby   │  │
│  │             │◀───────▶│  Service    │◀───────▶│             │  │
│  │  DB Master  │         │ (monitors)  │         │  DB Replica │  │
│  └──────┬──────┘         └──────┬──────┘         └─────────────┘  │
│         │                       │                                   │
│         │ Heartbeat             │                                   │
│         │ fails                 │                                   │
│         ✗                       │                                   │
│                                 │                                   │
│                                 ▼                                   │
│                          ┌─────────────────────────────────────┐   │
│                          │  Automatic actions:                  │   │
│                          │  1. Detect primary failure           │   │
│                          │  2. Verify (avoid false positive)    │   │
│                          │  3. Promote standby to primary       │   │
│                          │  4. Update DNS/VIP/config            │   │
│                          │  5. Alert operations team            │   │
│                          └─────────────────────────────────────┘   │
│                                                                      │
│  Pros:                              Cons:                           │
│  ✓ Fast recovery (seconds-minutes) ✗ Risk of false positives       │
│  ✓ No human intervention needed    ✗ Split-brain possible          │
│  ✓ 24/7 coverage                   ✗ Complex to implement correctly│
└─────────────────────────────────────────────────────────────────────┘
```

### 2. Manual Failover / Ручная отказоустойчивость

```
┌─────────────────────────────────────────────────────────────────────┐
│  MANUAL FAILOVER                                                    │
│                                                                      │
│  Process:                                                           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  1. Alert fires: "Primary unhealthy"                        │   │
│  │              ↓                                               │   │
│  │  2. On-call engineer paged                                   │   │
│  │              ↓                                               │   │
│  │  3. Engineer investigates:                                   │   │
│  │     - Is it really dead?                                     │   │
│  │     - Can it be recovered quickly?                          │   │
│  │     - What's the impact of failover?                        │   │
│  │              ↓                                               │   │
│  │  4. Decision: Failover or fix primary                       │   │
│  │              ↓                                               │   │
│  │  5. Execute runbook (if failover)                           │   │
│  │     - Promote standby                                        │   │
│  │     - Update routing                                         │   │
│  │     - Verify functionality                                   │   │
│  │              ↓                                               │   │
│  │  6. Post-incident review                                     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Pros:                              Cons:                           │
│  ✓ Human judgment involved         ✗ Slower (minutes-hours)        │
│  ✓ Avoids false positives          ✗ Requires 24/7 on-call         │
│  ✓ Can fix without failover        ✗ Human error possible          │
│  ✓ Appropriate for complex cases   ✗ Not suitable for mission-crit │
└─────────────────────────────────────────────────────────────────────┘
```

### 3. Semi-Automatic Failover / Полуавтоматическая отказоустойчивость

```
┌─────────────────────────────────────────────────────────────────────┐
│  SEMI-AUTOMATIC FAILOVER                                            │
│                                                                      │
│  Automated detection + Human approval + Automated execution        │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  1. System detects failure automatically                    │   │
│  │              ↓                                               │   │
│  │  2. System prepares failover plan                           │   │
│  │              ↓                                               │   │
│  │  3. Human receives alert with:                              │   │
│  │     - Diagnosis summary                                      │   │
│  │     - Recommended action                                     │   │
│  │     - One-click approval button                             │   │
│  │              ↓                                               │   │
│  │  4. Human approves (or investigates further)                │   │
│  │              ↓                                               │   │
│  │  5. System executes failover automatically                  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Best for: Mission-critical systems where you want human in loop   │
│  but can't afford long diagnosis time                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Graceful Degradation / Плавная деградация

### Concept / Концепция

Graceful degradation means the system continues operating with reduced functionality when components fail, rather than failing completely.

Плавная деградация означает, что система продолжает работать с ограниченной функциональностью при отказе компонентов, а не отказывает полностью.

### Patterns / Паттерны

```
┌─────────────────────────────────────────────────────────────────────┐
│  GRACEFUL DEGRADATION PATTERNS                                      │
│                                                                      │
│  1. FEATURE FLAGS                                                   │
│     ┌─────────────────────────────────────────────────────────┐    │
│     │  if recommendation_service.healthy:                      │    │
│     │      show_recommendations()                              │    │
│     │  else:                                                    │    │
│     │      show_popular_items()  # Fallback                   │    │
│     └─────────────────────────────────────────────────────────┘    │
│                                                                      │
│  2. CIRCUIT BREAKER                                                 │
│     ┌─────────────────────────────────────────────────────────┐    │
│     │  [CLOSED] ──failures exceed threshold──▶ [OPEN]         │    │
│     │     ▲                                        │           │    │
│     │     │                               timeout  │           │    │
│     │     │                                        ▼           │    │
│     │     └────────── success ────────── [HALF-OPEN]          │    │
│     │                                                          │    │
│     │  Open state: Return cached/default response immediately  │    │
│     │  Don't even try to call failing service                 │    │
│     └─────────────────────────────────────────────────────────┘    │
│                                                                      │
│  3. STATIC FALLBACK                                                 │
│     ┌─────────────────────────────────────────────────────────┐    │
│     │  CDN serves static version if origin fails               │    │
│     │  "Service temporarily unavailable" page                  │    │
│     │  Cached API responses when backend down                  │    │
│     └─────────────────────────────────────────────────────────┘    │
│                                                                      │
│  4. SHED LOAD                                                       │
│     ┌─────────────────────────────────────────────────────────┐    │
│     │  Under extreme load, prioritize:                         │    │
│     │  - Authenticated users over anonymous                    │    │
│     │  - Paid users over free users                           │    │
│     │  - Core features over analytics                          │    │
│     └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### Circuit Breaker Implementation / Реализация Circuit Breaker

```python
import time
from enum import Enum
from functools import wraps

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if recovered

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0

    def call(self, func, fallback=None):
        """Execute function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if self._should_try_recovery():
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
            else:
                return self._handle_open(fallback)

        try:
            result = func()
            self._handle_success()
            return result
        except Exception as e:
            self._handle_failure()
            if fallback:
                return fallback()
            raise

    def _should_try_recovery(self) -> bool:
        return (
            self.last_failure_time and
            time.time() - self.last_failure_time > self.recovery_timeout
        )

    def _handle_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.half_open_max_calls:
                # Recovered!
                self.state = CircuitState.CLOSED
                self.failure_count = 0

    def _handle_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            # Still failing, back to open
            self.state = CircuitState.OPEN
        elif self.failure_count >= self.failure_threshold:
            # Threshold exceeded, open circuit
            self.state = CircuitState.OPEN

    def _handle_open(self, fallback):
        if fallback:
            return fallback()
        raise CircuitOpenError("Circuit breaker is open")


# Usage
recommendation_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30)

def get_recommendations(user_id):
    return recommendation_breaker.call(
        lambda: recommendation_service.get(user_id),
        fallback=lambda: get_popular_items()  # Fallback
    )
```

---

## Disaster Recovery / Восстановление после катастроф

### DR Strategies / Стратегии DR

```
┌─────────────────────────────────────────────────────────────────────┐
│  DISASTER RECOVERY STRATEGIES                                       │
│                                                                      │
│  1. BACKUP AND RESTORE                                              │
│     Cost: $       RTO: Hours-Days    RPO: Hours-Days               │
│     ┌─────────────────────────────────────────────────────────┐    │
│     │  Primary DC              Backup Storage                  │    │
│     │  ┌─────────┐             ┌─────────┐                    │    │
│     │  │ Active  │────backup───│  S3/GCS │                    │    │
│     │  │ Systems │    daily    │ Backups │                    │    │
│     │  └─────────┘             └─────────┘                    │    │
│     │                               │                          │    │
│     │  On disaster: Provision new infra, restore backups       │    │
│     └─────────────────────────────────────────────────────────┘    │
│                                                                      │
│  2. PILOT LIGHT                                                     │
│     Cost: $$      RTO: Hours        RPO: Minutes               │
│     ┌─────────────────────────────────────────────────────────┐    │
│     │  Primary DC              DR Region                       │    │
│     │  ┌─────────┐             ┌─────────┐                    │    │
│     │  │ Active  │──replicate──│ Minimal │                    │    │
│     │  │ Systems │    async    │ DB only │ (pilot light)      │    │
│     │  └─────────┘             └─────────┘                    │    │
│     │                               │                          │    │
│     │  On disaster: Scale up DR infra around replicated DB     │    │
│     └─────────────────────────────────────────────────────────┘    │
│                                                                      │
│  3. WARM STANDBY                                                    │
│     Cost: $$$     RTO: Minutes      RPO: Seconds-Minutes           │
│     ┌─────────────────────────────────────────────────────────┐    │
│     │  Primary DC              DR Region                       │    │
│     │  ┌─────────┐             ┌─────────┐                    │    │
│     │  │ Active  │──replicate──│  Scaled │                    │    │
│     │  │ Systems │    sync     │  Down   │ (minimal capacity) │    │
│     │  └─────────┘             └─────────┘                    │    │
│     │                               │                          │    │
│     │  On disaster: Scale up, switch DNS                       │    │
│     └─────────────────────────────────────────────────────────┘    │
│                                                                      │
│  4. HOT STANDBY (Active-Active)                                    │
│     Cost: $$$$    RTO: Seconds      RPO: Zero                      │
│     ┌─────────────────────────────────────────────────────────┐    │
│     │  Primary DC              Secondary DC                    │    │
│     │  ┌─────────┐             ┌─────────┐                    │    │
│     │  │ Active  │◀──sync─────▶│ Active  │                    │    │
│     │  │ 50%     │  replicate  │ 50%     │                    │    │
│     │  └─────────┘             └─────────┘                    │    │
│     │        │                       │                         │    │
│     │        └───────────────────────┘                         │    │
│     │               Global Load Balancer                       │    │
│     │                                                          │    │
│     │  On disaster: Traffic automatically routes to surviving  │    │
│     └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### DR Testing / Тестирование DR

```
┌─────────────────────────────────────────────────────────────────────┐
│  DR TESTING TYPES                                                   │
│                                                                      │
│  1. TABLETOP EXERCISE                                               │
│     • Walk through DR plan on paper                                │
│     • Identify gaps in documentation                               │
│     • No actual systems affected                                    │
│     • Frequency: Quarterly                                         │
│                                                                      │
│  2. SIMULATION TEST                                                 │
│     • Simulate disaster scenario                                   │
│     • Execute recovery in test environment                         │
│     • Verify backups are restorable                                │
│     • Frequency: Semi-annually                                     │
│                                                                      │
│  3. PARALLEL TEST                                                   │
│     • Recover to DR site while primary runs                        │
│     • Verify functionality without affecting production            │
│     • Frequency: Annually                                          │
│                                                                      │
│  4. FULL FAILOVER TEST                                              │
│     • Actually failover to DR site                                 │
│     • Production traffic goes to DR                                │
│     • Highest risk, highest confidence                             │
│     • Frequency: Annually (planned maintenance window)             │
│                                                                      │
│  CHAOS ENGINEERING                                                  │
│     • Continuously inject failures in production                   │
│     • Netflix Chaos Monkey, Gremlin, LitmusChaos                  │
│     • Build confidence in system resilience                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Failover Checklist / Чеклист отказоустойчивости

```
┌─────────────────────────────────────────────────────────────────────┐
│  FAILOVER READINESS CHECKLIST                                       │
│                                                                      │
│  DOCUMENTATION                                                      │
│  □ Runbooks for each failover scenario                             │
│  □ Contact list (on-call, stakeholders)                            │
│  □ Dependency map                                                   │
│  □ Recovery procedures documented                                  │
│                                                                      │
│  MONITORING                                                         │
│  □ Health checks on all critical services                          │
│  □ Alerts for failure indicators                                   │
│  □ Dashboard for failover status                                   │
│  □ Log aggregation for troubleshooting                            │
│                                                                      │
│  AUTOMATION                                                         │
│  □ Automated failover scripts tested                               │
│  □ DNS/VIP update automation                                       │
│  □ Database promotion scripts                                      │
│  □ Configuration sync between primary/standby                      │
│                                                                      │
│  DATA                                                               │
│  □ Replication lag monitoring                                      │
│  □ Backup verification (restore tests)                             │
│  □ Data consistency checks                                         │
│                                                                      │
│  TESTING                                                            │
│  □ Regular failover drills scheduled                               │
│  □ Last successful failover test date: ________                    │
│  □ Issues from last test resolved: □                               │
│                                                                      │
│  COMMUNICATION                                                      │
│  □ Status page integration                                         │
│  □ Customer notification templates                                 │
│  □ Internal communication plan                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Связано с

- [[HA-Patterns]]
- [[Consensus]]

## Ресурсы

- [AWS Disaster Recovery Whitepaper](https://docs.aws.amazon.com/whitepapers/latest/disaster-recovery-workloads-on-aws/)
- [Google SRE Book - Handling Overload](https://sre.google/sre-book/handling-overload/)
- [Release It! - Michael Nygard](https://pragprog.com/titles/mnee2/release-it-second-edition/)
- [Circuit Breaker Pattern - Martin Fowler](https://martinfowler.com/bliki/CircuitBreaker.html)

---
tags:
  - system-design
  - high-availability
  - raft
  - paxos
created: 2026-02-17
---

# Consensus Algorithms Overview / Обзор алгоритмов консенсуса

> **Reading time:** ~18 min | **Время чтения:** ~18 мин

## Что это

Обзор алгоритмов консенсуса в распределённых системах: [[Raft]], Paxos, ZAB. Выбор лидера, репликация лога, кворум, FLP Impossibility. Практическое сравнение и применение в etcd, Consul, ZooKeeper, CockroachDB.

**Consensus** is the problem of getting multiple nodes to agree on a single value in a distributed system, even in the presence of failures.

**Консенсус** — это проблема достижения согласия между несколькими узлами о едином значении в распределённой системе, даже при наличии отказов.

---

## Why is Consensus Hard? / Почему консенсус сложен?

```
┌─────────────────────────────────────────────────────────────────────┐
│  THE CONSENSUS PROBLEM                                              │
│                                                                      │
│  Challenges:                                                        │
│  1. Network can partition (nodes can't communicate)                │
│  2. Messages can be delayed, reordered, or lost                    │
│  3. Nodes can crash and restart                                    │
│  4. Clocks can drift (no global time)                             │
│                                                                      │
│  Requirements (Safety):                                             │
│  • Agreement: All nodes decide on the same value                   │
│  • Validity: Decided value was proposed by some node               │
│  • Integrity: Each node decides at most once                       │
│                                                                      │
│  Requirements (Liveness):                                           │
│  • Termination: All non-faulty nodes eventually decide             │
│                                                                      │
│  FLP Impossibility (1985):                                          │
│  In an asynchronous system with even ONE faulty node,              │
│  it's IMPOSSIBLE to guarantee both safety AND liveness.            │
│  → Real systems use timeouts to work around this                   │
└─────────────────────────────────────────────────────────────────────┘
```

### Consensus Use Cases / Сценарии применения

| Use Case | Why Consensus Needed |
|----------|---------------------|
| Leader election | Only one leader at a time |
| Distributed locks | Only one holder at a time |
| Atomic broadcast | All nodes see messages in same order |
| Replicated state machines | All replicas have same state |
| Configuration management | All nodes agree on config |

---

## Raft Consensus / Консенсус Raft

### Overview / Обзор

**Raft** (2014) was designed to be understandable, unlike Paxos. It's used in etcd, Consul, CockroachDB, and TiDB.

**Raft** (2014) был разработан для понятности, в отличие от Paxos. Используется в etcd, Consul, CockroachDB, TiDB.

### Node States / Состояния узлов

```
┌─────────────────────────────────────────────────────────────────────┐
│  RAFT NODE STATES                                                   │
│                                                                      │
│                    ┌──────────────────┐                            │
│       starts up    │    FOLLOWER      │   times out                │
│       ──────────▶  │                  │   ──────────▶              │
│                    │  Receives logs   │                            │
│                    │  from leader     │                            │
│                    └────────┬─────────┘                            │
│                             │                                       │
│                             │ election timeout                      │
│                             │ (no leader heartbeat)                 │
│                             ▼                                       │
│                    ┌──────────────────┐                            │
│                    │   CANDIDATE      │                            │
│       ◀────────    │                  │   ──────────▶              │
│       loses        │  Requests votes  │   wins election            │
│       election     │  from others     │   (majority)               │
│                    └────────┬─────────┘                            │
│                             │                                       │
│                             │ receives majority votes               │
│                             ▼                                       │
│                    ┌──────────────────┐                            │
│                    │    LEADER        │                            │
│                    │                  │                            │
│                    │  Sends heartbeats│                            │
│                    │  Replicates logs │                            │
│                    └──────────────────┘                            │
│                             │                                       │
│                             │ discovers higher term                 │
│                             ▼                                       │
│                       (reverts to Follower)                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Leader Election / Выбор лидера

```
┌─────────────────────────────────────────────────────────────────────┐
│  RAFT LEADER ELECTION                                               │
│                                                                      │
│  Term 1: Node A is leader                                          │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                            │
│  │ Node A  │  │ Node B  │  │ Node C  │                            │
│  │ LEADER  │  │FOLLOWER │  │FOLLOWER │                            │
│  │ term=1  │  │ term=1  │  │ term=1  │                            │
│  └────┬────┘  └─────────┘  └─────────┘                            │
│       │                                                             │
│       │ heartbeat                                                   │
│       └─────────────────────────────▶                              │
│                                                                      │
│  Node A crashes!                                                    │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                            │
│  │ Node A  │  │ Node B  │  │ Node C  │                            │
│  │  DEAD   │  │FOLLOWER │  │FOLLOWER │                            │
│  │   ✗     │  │ term=1  │  │ term=1  │                            │
│  └─────────┘  └────┬────┘  └─────────┘                            │
│                    │                                                │
│                    │ election timeout expires                       │
│                    ▼                                                │
│  Term 2: Node B becomes candidate                                  │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                            │
│  │ Node A  │  │ Node B  │  │ Node C  │                            │
│  │  DEAD   │  │CANDIDATE│◀─│FOLLOWER │                            │
│  │   ✗     │  │ term=2  │  │ term=1  │                            │
│  └─────────┘  │ votes=1 │  │         │                            │
│               └────┬────┘  └────┬────┘                            │
│                    │            │                                   │
│                    │ RequestVote│                                   │
│                    │───────────▶│                                   │
│                    │◀───────────│ Vote granted (B's log up-to-date)│
│                    │            │                                   │
│                    ▼                                                │
│  Node B becomes leader (has 2 votes out of 3)                      │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                            │
│  │ Node A  │  │ Node B  │  │ Node C  │                            │
│  │  DEAD   │  │ LEADER  │  │FOLLOWER │                            │
│  │   ✗     │  │ term=2  │  │ term=2  │                            │
│  └─────────┘  └─────────┘  └─────────┘                            │
└─────────────────────────────────────────────────────────────────────┘
```

### Log Replication / Репликация лога

```
┌─────────────────────────────────────────────────────────────────────┐
│  RAFT LOG REPLICATION                                               │
│                                                                      │
│  Leader receives write request                                      │
│                                                                      │
│  1. Leader appends to local log (uncommitted)                      │
│  ┌─────────┐                                                        │
│  │ Leader  │ Log: [1:x=1, 2:y=2, 3:z=3*]  (* = uncommitted)       │
│  └────┬────┘                                                        │
│       │                                                             │
│  2. Leader sends AppendEntries to followers                        │
│       │  AppendEntries(entry 3)                                    │
│       ├──────────────────────────▶ Follower A                      │
│       ├──────────────────────────▶ Follower B                      │
│       │                                                             │
│  3. Followers append to their logs                                 │
│  ┌────────────┐  ┌────────────┐                                    │
│  │ Follower A │  │ Follower B │                                    │
│  │ [1,2,3*]   │  │ [1,2,3*]   │                                    │
│  └─────┬──────┘  └─────┬──────┘                                    │
│        │               │                                            │
│  4. Followers acknowledge                                           │
│        │    ACK        │    ACK                                    │
│        └───────────────┴───────────▶ Leader                        │
│                                                                      │
│  5. Leader receives majority ACKs → commits entry                  │
│  ┌─────────┐                                                        │
│  │ Leader  │ Log: [1:x=1, 2:y=2, 3:z=3✓]  (✓ = committed)         │
│  └────┬────┘                                                        │
│       │                                                             │
│  6. Leader notifies followers of commit                            │
│       │  (in next AppendEntries or heartbeat)                      │
│       └──────────────────────────▶ Followers apply committed entry │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Paxos / Паксос

### Overview / Обзор

**Paxos** (1989, published 1998) is the foundational consensus algorithm. It's notoriously difficult to understand but mathematically proven correct.

**Paxos** (1989, опубликован 1998) — это фундаментальный алгоритм консенсуса. Известен своей сложностью для понимания, но математически доказан.

### Basic Paxos Roles / Роли в Basic Paxos

```
┌─────────────────────────────────────────────────────────────────────┐
│  PAXOS ROLES                                                        │
│                                                                      │
│  PROPOSER                                                           │
│  • Proposes values                                                  │
│  • Drives consensus process                                         │
│                                                                      │
│  ACCEPTOR                                                           │
│  • Votes on proposals                                               │
│  • Stores accepted values                                           │
│  • Quorum of acceptors required                                    │
│                                                                      │
│  LEARNER                                                            │
│  • Learns decided value                                             │
│  • Doesn't participate in voting                                   │
│                                                                      │
│  Note: In practice, one node often plays all three roles           │
└─────────────────────────────────────────────────────────────────────┘
```

### Two-Phase Protocol / Двухфазный протокол

```
┌─────────────────────────────────────────────────────────────────────┐
│  BASIC PAXOS TWO-PHASE PROTOCOL                                    │
│                                                                      │
│  Phase 1a: PREPARE                                                  │
│  ┌──────────┐                                                       │
│  │ Proposer │──Prepare(n)──▶ Acceptors                             │
│  └──────────┘  "I want to propose with number n"                   │
│                                                                      │
│  Phase 1b: PROMISE                                                  │
│  ┌──────────┐                                                       │
│  │ Acceptor │──Promise(n, v?)──▶ Proposer                          │
│  └──────────┘  "I promise not to accept proposals < n"             │
│               "Here's the highest value v I've accepted (if any)"  │
│                                                                      │
│  Phase 2a: ACCEPT                                                   │
│  ┌──────────┐                                                       │
│  │ Proposer │──Accept(n, v)──▶ Acceptors                           │
│  └──────────┘  "Please accept value v with proposal number n"      │
│               (v = highest v from promises, or proposer's value)   │
│                                                                      │
│  Phase 2b: ACCEPTED                                                 │
│  ┌──────────┐                                                       │
│  │ Acceptor │──Accepted(n, v)──▶ Learners                          │
│  └──────────┘  "I accepted value v with number n"                  │
│                                                                      │
│  When majority of acceptors accept same (n, v) → value is decided  │
└─────────────────────────────────────────────────────────────────────┘
```

### Paxos vs Raft / Paxos vs Raft

| Aspect | Paxos | Raft |
|--------|-------|------|
| Understandability | Very difficult | Designed for clarity |
| Leader | Optional (Multi-Paxos) | Required |
| Safety proof | Rigorous | Rigorous |
| Liveness | Relies on stable leader | Built-in leader election |
| Implementations | Chubby, Spanner | etcd, Consul |
| Log compaction | Separate concern | Built-in (snapshots) |

---

## ZAB (ZooKeeper Atomic Broadcast) / ZAB

### Overview / Обзор

**ZAB** is the consensus protocol used by Apache ZooKeeper. It's similar to Paxos but optimized for primary-backup replication.

**ZAB** — протокол консенсуса Apache ZooKeeper. Похож на Paxos, но оптимизирован для репликации primary-backup.

```
┌─────────────────────────────────────────────────────────────────────┐
│  ZAB PROTOCOL                                                       │
│                                                                      │
│  Two modes:                                                         │
│                                                                      │
│  1. BROADCAST MODE (normal operation)                               │
│     ┌────────┐     propose      ┌──────────┐                       │
│     │ Client │──────────────────▶│  Leader  │                       │
│     └────────┘                   └────┬─────┘                       │
│                                       │                             │
│                         ┌─────────────┼─────────────┐               │
│                         ▼             ▼             ▼               │
│                    ┌────────┐   ┌────────┐   ┌────────┐           │
│                    │Follower│   │Follower│   │Follower│           │
│                    └───┬────┘   └───┬────┘   └───┬────┘           │
│                        │            │            │                  │
│                        └────────────┼────────────┘                  │
│                                     ▼                               │
│                              Majority ACK                           │
│                                     │                               │
│                              Leader COMMIT                          │
│                                                                      │
│  2. RECOVERY MODE (leader election)                                 │
│     When leader fails:                                              │
│     • Elect new leader with highest zxid                           │
│     • Synchronize all followers to new leader                      │
│     • Resume broadcast mode                                         │
│                                                                      │
│  ZXID (Transaction ID):                                            │
│  64-bit: [32-bit epoch][32-bit counter]                           │
│  Epoch increments on each leader election                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Practical Comparison / Практическое сравнение

### Algorithm Comparison / Сравнение алгоритмов

```
┌─────────────────────────────────────────────────────────────────────┐
│  CONSENSUS ALGORITHMS COMPARISON                                    │
│                                                                      │
│  Algorithm │ Leader │ Rounds │ Used By                              │
│  ──────────┼────────┼────────┼──────────────────────────────────── │
│  Paxos     │ Optional│ 2+    │ Google Chubby, Spanner              │
│  Raft      │ Required│ 2     │ etcd, Consul, CockroachDB           │
│  ZAB       │ Required│ 2     │ ZooKeeper                           │
│  Viewstamped│Required│ 2     │ Research, some DBs                  │
│                                                                      │
│  Fault tolerance: All tolerate (N-1)/2 failures for N nodes        │
│  Minimum cluster: 3 nodes (tolerate 1 failure)                     │
│  Recommended: 5 nodes (tolerate 2 failures)                        │
│                                                                      │
│  Performance characteristics:                                       │
│  • Leader-based: 1 RTT for writes (2 for Paxos)                   │
│  • Throughput limited by leader                                    │
│  • Read from followers may be stale                                │
└─────────────────────────────────────────────────────────────────────┘
```

### Systems Using Consensus / Системы, использующие консенсус

| System | Algorithm | Use Case |
|--------|-----------|----------|
| etcd | Raft | Kubernetes config, service discovery |
| Consul | Raft | Service mesh, KV store |
| ZooKeeper | ZAB | Coordination, leader election |
| CockroachDB | Raft | Distributed SQL |
| TiDB | Raft | Distributed SQL |
| Google Spanner | Paxos | Global SQL |
| Kafka (KRaft) | Raft | Metadata management |
| [[Redpanda]] | Raft | Metadata management |

---

## Quorum Math / Математика кворума

```
┌─────────────────────────────────────────────────────────────────────┐
│  QUORUM CALCULATIONS                                                │
│                                                                      │
│  For N nodes, quorum = floor(N/2) + 1                              │
│                                                                      │
│  N nodes │ Quorum │ Tolerates failures │ Notes                     │
│  ────────┼────────┼────────────────────┼────────────────────────── │
│  1       │ 1      │ 0                  │ No fault tolerance        │
│  2       │ 2      │ 0                  │ Worse than 1 (both needed)│
│  3       │ 2      │ 1                  │ Minimum for HA            │
│  4       │ 3      │ 1                  │ Same as 3, wastes 1 node  │
│  5       │ 3      │ 2                  │ Recommended for prod      │
│  6       │ 4      │ 2                  │ Same as 5, wastes 1 node  │
│  7       │ 4      │ 3                  │ Higher availability       │
│                                                                      │
│  Observation: Odd numbers are more efficient                       │
│  (even numbers require same quorum as N+1)                         │
│                                                                      │
│  CAP Theorem connection:                                            │
│  • During partition: only majority partition can make progress     │
│  • Minority partition becomes unavailable (CP choice)              │
│  • This prevents split-brain                                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Interview Questions / Вопросы для интервью

### Q: Why do we need odd number of nodes?
**Почему нужно нечётное количество узлов?**

**Answer:** With N nodes, we need N/2+1 for quorum.
- 3 nodes: quorum = 2, tolerates 1 failure
- 4 nodes: quorum = 3, tolerates 1 failure (same!)
- 5 nodes: quorum = 3, tolerates 2 failures

Even numbers waste a node without improving fault tolerance.

### Q: What happens during network partition?
**Что происходит при сетевом разделении?**

**Answer:** Only the partition with majority can continue. The minority partition:
- Cannot elect new leader (not enough votes)
- Cannot commit new writes (not enough ACKs)
- Becomes read-only or unavailable

This is by design to prevent split-brain.

### Q: How does Raft handle a slow follower?
**Как Raft обрабатывает медленного follower?**

**Answer:** Leader tracks each follower's `nextIndex` and `matchIndex`. If follower is behind:
1. Leader decrements `nextIndex` for that follower
2. Sends earlier log entries
3. Follower catches up at its own pace
4. Leader continues with majority (slow follower doesn't block writes)

## Связано с

- [[HA-Patterns]]
- [[Kafka]]

## Ресурсы

- [Raft Paper](https://raft.github.io/raft.pdf) -- In Search of an Understandable Consensus Algorithm
- [Paxos Made Simple](https://lamport.azurewebsites.net/pubs/paxos-simple.pdf) -- Leslie Lamport
- [ZooKeeper ZAB](https://zookeeper.apache.org/doc/r3.4.13/zookeeperInternals.html)
- [Raft Visualization](https://raft.github.io/)
- [Designing Data-Intensive Applications](https://dataintensive.net/) -- Chapter 9

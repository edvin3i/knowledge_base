---
tags:
  - system-design
  - databases
  - sharding
  - replication
created: 2026-02-17
---

## Что это

Шардинг и репликация — две фундаментальные стратегии горизонтального масштабирования баз данных. Репликация копирует данные на несколько узлов для доступности и масштабирования чтения. Шардинг разделяет данные между узлами для масштабирования записи и распределения данных.

---

# Sharding and Replication: Horizontal Scaling Strategies
# Шардинг и репликация: Стратегии горизонтального масштабирования

> **Reading time:** ~18 min | **Время чтения:** ~18 мин

---

## Introduction / Введение

As data grows beyond single-node capacity, databases must scale horizontally. This document covers two fundamental techniques: replication (for read scaling and availability) and sharding (for write scaling and data distribution).

Когда данные превышают ёмкость одного узла, базы данных должны масштабироваться горизонтально. Этот документ рассматривает две фундаментальные техники: репликацию (для масштабирования чтения и доступности) и шардинг (для масштабирования записи и распределения данных).

---

## Replication / Репликация

### What is Replication? / Что такое репликация?

Replication copies data across multiple nodes to improve availability and read performance.

Репликация копирует данные на несколько узлов для улучшения доступности и производительности чтения.

```
┌─────────────────────────────────────────────────────────────────────┐
│                      REPLICATION OVERVIEW                            │
│                                                                      │
│  Single Node (No Replication)                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    ┌──────────┐                              │    │
│  │   Clients ──────►  │  Primary │  ◄─── Single Point of       │    │
│  │                    │   Node   │       Failure (SPOF)         │    │
│  │                    └──────────┘                              │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  With Replication                                                   │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    ┌──────────┐                              │    │
│  │   Writes ────────► │  Primary │ ◄─── Handles all writes     │    │
│  │                    │   Node   │                              │    │
│  │                    └────┬─────┘                              │    │
│  │                         │ Replication                        │    │
│  │            ┌────────────┼────────────┐                      │    │
│  │            ▼            ▼            ▼                      │    │
│  │       ┌────────┐   ┌────────┐   ┌────────┐                  │    │
│  │       │Replica │   │Replica │   │Replica │                  │    │
│  │       │   1    │   │   2    │   │   3    │                  │    │
│  │       └────────┘   └────────┘   └────────┘                  │    │
│  │            ▲            ▲            ▲                      │    │
│  │            └────────────┴────────────┘                      │    │
│  │                         │                                    │    │
│  │   Reads ────────────────┘  Distributed across replicas      │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  Benefits:                                                          │
│  • High Availability: Primary fails → promote replica               │
│  • Read Scaling: Distribute reads across replicas                   │
│  • Disaster Recovery: Replicas in different data centers           │
└─────────────────────────────────────────────────────────────────────┘
```

### Synchronous vs Asynchronous Replication / Синхронная vs асинхронная репликация

```
┌─────────────────────────────────────────────────────────────────────┐
│                   REPLICATION STRATEGIES                             │
│                                                                      │
│  SYNCHRONOUS REPLICATION                                            │
│  ──────────────────────────────────────────────────────────────────│
│                                                                      │
│  Client        Primary         Replica 1       Replica 2            │
│    │              │                │               │                 │
│    │──WRITE──────►│                │               │                 │
│    │              │───REPLICATE───►│               │                 │
│    │              │───REPLICATE────────────────────►│                │
│    │              │                │               │                 │
│    │              │◄──────ACK──────│               │                 │
│    │              │◄───────────────ACK─────────────│                 │
│    │◄────ACK──────│                │               │                 │
│    │              │                │               │                 │
│                                                                      │
│  • Write confirmed only after ALL replicas acknowledge              │
│  • Strong consistency: no data loss on primary failure              │
│  • Higher latency: wait for slowest replica                         │
│  • Used: PostgreSQL synchronous_commit, MySQL semi-sync             │
│                                                                      │
│  ──────────────────────────────────────────────────────────────────│
│                                                                      │
│  ASYNCHRONOUS REPLICATION                                           │
│  ──────────────────────────────────────────────────────────────────│
│                                                                      │
│  Client        Primary         Replica 1       Replica 2            │
│    │              │                │               │                 │
│    │──WRITE──────►│                │               │                 │
│    │◄────ACK──────│  (immediate)   │               │                 │
│    │              │                │               │                 │
│    │              │───REPLICATE───►│  (background) │                 │
│    │              │───REPLICATE────────────────────►│ (background)   │
│    │              │                │               │                 │
│                                                                      │
│  • Write confirmed immediately after primary write                  │
│  • Eventual consistency: replicas may lag                           │
│  • Lower latency                                                    │
│  • Risk: Primary fails → uncommitted writes lost (replication lag)  │
│  • Used: MongoDB default, PostgreSQL streaming replication          │
└─────────────────────────────────────────────────────────────────────┘
```

### Replication Topologies / Топологии репликации

```
┌─────────────────────────────────────────────────────────────────────┐
│                    REPLICATION TOPOLOGIES                            │
│                                                                      │
│  1. PRIMARY-REPLICA (Master-Slave)                                  │
│     ────────────────────────────────────                            │
│                                                                      │
│     ┌─────────┐                                                     │
│     │ Primary │ ◄── All writes                                      │
│     └────┬────┘                                                     │
│          │                                                          │
│     ┌────┴────────────────┐                                        │
│     │         │           │                                         │
│     ▼         ▼           ▼                                         │
│  ┌──────┐ ┌──────┐  ┌──────┐                                       │
│  │Replica│ │Replica│ │Replica│ ◄── Reads distributed               │
│  └──────┘ └──────┘  └──────┘                                       │
│                                                                      │
│  Pros: Simple, well-understood                                      │
│  Cons: Write bottleneck on primary                                  │
│                                                                      │
│  2. MULTI-PRIMARY (Master-Master)                                   │
│     ─────────────────────────────                                   │
│                                                                      │
│     ┌──────────┐         ┌──────────┐                               │
│     │ Primary A│ ◄──────►│ Primary B│                               │
│     └────┬─────┘         └────┬─────┘                               │
│          │                    │                                     │
│     Writes OK            Writes OK                                  │
│                                                                      │
│  Pros: No single write bottleneck                                   │
│  Cons: Conflict resolution needed                                   │
│                                                                      │
│  3. CHAIN REPLICATION                                               │
│     ─────────────────────                                           │
│                                                                      │
│     Writes ──► [Head] ──► [Middle] ──► [Tail] ──► Reads            │
│                                                                      │
│  Pros: Strong consistency, read from tail                           │
│  Cons: Higher latency, chain breaks problematic                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Sharding (Partitioning) / Шардинг (Партиционирование)

### What is Sharding? / Что такое шардинг?

Sharding splits data across multiple nodes, each holding a subset of the data.

Шардинг разделяет данные между несколькими узлами, каждый из которых содержит подмножество данных.

```
┌─────────────────────────────────────────────────────────────────────┐
│                       SHARDING OVERVIEW                              │
│                                                                      │
│  Without Sharding (Single Node)                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │         ┌────────────────────────────────────────┐           │    │
│  │         │           Single Database              │           │    │
│  │         │  ┌────────────────────────────────┐   │           │    │
│  │         │  │ 1TB of data, 10K writes/sec   │   │           │    │
│  │         │  │ CPU, Memory, I/O saturated     │   │           │    │
│  │         │  └────────────────────────────────┘   │           │    │
│  │         └────────────────────────────────────────┘           │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  With Sharding                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  ┌──────────┐     ┌──────────┐     ┌──────────┐             │    │
│  │  │ Shard 1  │     │ Shard 2  │     │ Shard 3  │             │    │
│  │  │          │     │          │     │          │             │    │
│  │  │ 333GB    │     │ 333GB    │     │ 333GB    │             │    │
│  │  │ Users    │     │ Users    │     │ Users    │             │    │
│  │  │ A-H      │     │ I-P      │     │ Q-Z      │             │    │
│  │  │ 3.3K w/s │     │ 3.3K w/s │     │ 3.3K w/s │             │    │
│  │  └──────────┘     └──────────┘     └──────────┘             │    │
│  │                                                               │    │
│  │  Total: 1TB, 10K writes/sec distributed across 3 nodes       │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  Benefits:                                                          │
│  • Horizontal scaling of writes                                     │
│  • Each shard holds less data (faster queries)                      │
│  • Parallel query execution across shards                           │
│  • Independent failure domains                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Sharding Strategies / Стратегии шардинга

#### 1. Range-Based Sharding / Шардинг по диапазону

```
┌─────────────────────────────────────────────────────────────────────┐
│                     RANGE-BASED SHARDING                             │
│                                                                      │
│  Partition key: user_id                                             │
│                                                                      │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐               │
│  │   Shard 1   │   │   Shard 2   │   │   Shard 3   │               │
│  │             │   │             │   │             │               │
│  │  user_id    │   │  user_id    │   │  user_id    │               │
│  │  1 - 1000   │   │ 1001 - 2000 │   │ 2001 - 3000 │               │
│  │             │   │             │   │             │               │
│  └─────────────┘   └─────────────┘   └─────────────┘               │
│                                                                      │
│  Pros:                                                              │
│  • Range queries efficient (all data on one shard)                  │
│  • Simple to understand                                             │
│                                                                      │
│  Cons:                                                              │
│  • Hot spots: new users (high IDs) go to one shard                 │
│  • Uneven distribution possible                                     │
│                                                                      │
│  Good for: Time-series data (partition by month)                    │
│  Bad for: Sequential ID workloads (all writes to latest shard)     │
└─────────────────────────────────────────────────────────────────────┘
```

#### 2. Hash-Based Sharding / Хэш-шардинг

```
┌─────────────────────────────────────────────────────────────────────┐
│                      HASH-BASED SHARDING                             │
│                                                                      │
│  shard_id = hash(user_id) % num_shards                              │
│                                                                      │
│  Example: 3 shards                                                  │
│                                                                      │
│  user_id=123 → hash(123) = 456789 → 456789 % 3 = 0 → Shard 0       │
│  user_id=124 → hash(124) = 789012 → 789012 % 3 = 1 → Shard 1       │
│  user_id=125 → hash(125) = 234567 → 234567 % 3 = 2 → Shard 2       │
│                                                                      │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐               │
│  │   Shard 0   │   │   Shard 1   │   │   Shard 2   │               │
│  │             │   │             │   │             │               │
│  │  user 123   │   │  user 124   │   │  user 125   │               │
│  │  user 126   │   │  user 127   │   │  user 128   │               │
│  │  ...        │   │  ...        │   │  ...        │               │
│  └─────────────┘   └─────────────┘   └─────────────┘               │
│                                                                      │
│  Pros:                                                              │
│  • Even distribution (good hash function)                           │
│  • No hot spots from sequential data                                │
│                                                                      │
│  Cons:                                                              │
│  • Range queries require querying ALL shards                        │
│  • Resharding is painful (all data moves)                           │
└─────────────────────────────────────────────────────────────────────┘
```

#### 3. Consistent Hashing / Консистентное хэширование

```
┌─────────────────────────────────────────────────────────────────────┐
│                      CONSISTENT HASHING                              │
│                                                                      │
│  Problem with simple hash: Adding shard 4 to 3-shard cluster        │
│                                                                      │
│  Simple hash: hash(key) % 3 → hash(key) % 4                        │
│  Result: ~75% of data must move (3/4 keys change shard)            │
│                                                                      │
│  CONSISTENT HASHING SOLUTION                                        │
│  ────────────────────────────────────────────────────────────────── │
│                                                                      │
│  Nodes and keys placed on a ring (0 to 2^32):                       │
│                                                                      │
│                         0 / 2^32                                     │
│                            ●                                         │
│                     ╱            ╲                                   │
│                   ╱                ╲                                 │
│                 ╱      [Node A]     ╲                                │
│                ●          ●          ●                               │
│           [key1]                  [Node B]                           │
│              │                       │                               │
│              │                       │                               │
│              ●          ●           ●                                │
│           [key2]    [Node C]    [key3]                              │
│                ╲                ╱                                    │
│                  ╲            ╱                                      │
│                    ╲        ╱                                        │
│                      ● ── ●                                          │
│                                                                      │
│  Key assignment: Walk clockwise to find first node                  │
│  key1 → Node A, key2 → Node C, key3 → Node B                       │
│                                                                      │
│  ADDING NODE D                                                      │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                      │
│  Only keys between C and D move to D                                │
│  Other keys stay in place!                                          │
│                                                                      │
│                ●          ●                                          │
│           [key1]    [Node A]                                        │
│              │                                                       │
│              │       [Node D] ← New node                            │
│              │          ●                                            │
│              ●                ●                                      │
│           [key2]           [Node B]                                 │
│                ●                                                     │
│           [Node C]                                                   │
│                                                                      │
│  Only ~1/N keys move (where N = number of nodes)                    │
│  With 4 nodes: ~25% data moves (vs 75% with simple hash)           │
└─────────────────────────────────────────────────────────────────────┘
```

### Virtual Nodes (VNodes) / Виртуальные узлы

```
┌─────────────────────────────────────────────────────────────────────┐
│                        VIRTUAL NODES                                 │
│                                                                      │
│  Problem: Consistent hashing with few nodes → uneven distribution   │
│                                                                      │
│  Solution: Each physical node owns multiple virtual nodes (tokens)  │
│                                                                      │
│  Physical Node A owns: vnode_A1, vnode_A2, vnode_A3, ...           │
│  Physical Node B owns: vnode_B1, vnode_B2, vnode_B3, ...           │
│                                                                      │
│                            Ring                                      │
│                              ●                                       │
│                         ╱         ╲                                  │
│                       ╱             ╲                                │
│                     ●    A1    B2    ●                               │
│                  B1 │                │ A2                            │
│                     │                │                               │
│                     ●    A3    B1    ●                               │
│                       ╲             ╱                                │
│                         ╲         ╱                                  │
│                            ●                                         │
│                           A2                                         │
│                                                                      │
│  Benefits:                                                          │
│  • Better load distribution                                         │
│  • When node fails, load spreads across many nodes                  │
│  • Easy rebalancing (move vnodes, not all data)                     │
│                                                                      │
│  Used in: Cassandra, DynamoDB, Riak                                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Shard Key Selection / Выбор ключа шардинга

Choosing the right shard key is critical for performance and scalability.

Выбор правильного ключа шардинга критически важен для производительности и масштабируемости.

```
┌─────────────────────────────────────────────────────────────────────┐
│                      SHARD KEY SELECTION                             │
│                                                                      │
│  GOOD SHARD KEY PROPERTIES                                          │
│  ───────────────────────────────────────────────────────────────── │
│  1. High Cardinality                                                │
│     • Many unique values = better distribution                      │
│     • Bad: country (few values)                                     │
│     • Good: user_id (millions of values)                            │
│                                                                      │
│  2. Even Distribution                                               │
│     • Write load spread across shards                               │
│     • Bad: timestamp (recent data is hot)                           │
│     • Good: hash(user_id)                                           │
│                                                                      │
│  3. Query Pattern Alignment                                         │
│     • Common queries should hit single shard                        │
│     • If queries always filter by org_id, shard by org_id          │
│                                                                      │
│  4. Immutable                                                       │
│     • Changing shard key = moving data between shards              │
│     • Good: user_id (never changes)                                 │
│     • Bad: status (changes frequently)                              │
│                                                                      │
│  EXAMPLES                                                           │
│  ───────────────────────────────────────────────────────────────── │
│                                                                      │
│  Polyvision detections table:                                       │
│  Shard key: organization_id                                         │
│  • Multi-tenant: each org's data isolated                           │
│  • Queries always filter by org_id (tenant isolation)               │
│  • Orgs have varying sizes (some imbalance acceptable)              │
│                                                                      │
│  E-commerce orders:                                                 │
│  Shard key: customer_id                                             │
│  • Customer views their own orders (single shard query)             │
│  • Even distribution across customers                               │
│  • NOT order_id (random access pattern)                             │
│                                                                      │
│  Time series metrics:                                               │
│  Shard key: (device_id, time_bucket)                               │
│  • Compound key for better distribution                             │
│  • Range queries on time still efficient within device              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Replication + Sharding Combined / Репликация + Шардинг

Production systems combine both for availability AND scalability.

Продакшн-системы комбинируют оба подхода для доступности И масштабируемости.

```
┌─────────────────────────────────────────────────────────────────────┐
│                  SHARDING + REPLICATION                              │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                       Shard 1                                  │  │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐                │  │
│  │  │ Primary  │───►│ Replica  │───►│ Replica  │                │  │
│  │  │  S1-P    │    │  S1-R1   │    │  S1-R2   │                │  │
│  │  └──────────┘    └──────────┘    └──────────┘                │  │
│  │  Data: users A-H                                              │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                       Shard 2                                  │  │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐                │  │
│  │  │ Primary  │───►│ Replica  │───►│ Replica  │                │  │
│  │  │  S2-P    │    │  S2-R1   │    │  S2-R2   │                │  │
│  │  └──────────┘    └──────────┘    └──────────┘                │  │
│  │  Data: users I-P                                              │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                       Shard 3                                  │  │
│  │  ┌──────────┐    ┌──────────┐    ┌──────────┐                │  │
│  │  │ Primary  │───►│ Replica  │───►│ Replica  │                │  │
│  │  │  S3-P    │    │  S3-R1   │    │  S3-R2   │                │  │
│  │  └──────────┘    └──────────┘    └──────────┘                │  │
│  │  Data: users Q-Z                                              │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  Total: 9 nodes (3 shards × 3 replicas each)                       │
│  Write scaling: 3x (one primary per shard)                         │
│  Read scaling: 9x (reads from any replica)                         │
│  Fault tolerance: Any 2 nodes per shard can fail                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Database-Specific Implementations / Реализации в базах данных

### ClickHouse Sharding / Шардинг в ClickHouse

```sql
-- ClickHouse distributed table setup

-- 1. Create local table on each shard
CREATE TABLE detections_local ON CLUSTER 'polyvision_cluster' (
    organization_id UUID,
    match_id UUID,
    frame_idx UInt32,
    class_id UInt8,
    x Float32,
    y Float32,
    created_at DateTime
)
ENGINE = ReplicatedMergeTree('/clickhouse/tables/{shard}/detections', '{replica}')
PARTITION BY toYYYYMM(created_at)
ORDER BY (organization_id, match_id, frame_idx);

-- 2. Create distributed table (routes queries to shards)
CREATE TABLE detections ON CLUSTER 'polyvision_cluster' (
    -- same schema
)
ENGINE = Distributed(
    'polyvision_cluster',           -- cluster name
    'default',                       -- database
    'detections_local',              -- local table
    sipHash64(organization_id)       -- sharding key
);

-- Queries to 'detections' are automatically routed/merged
SELECT count(*) FROM detections
WHERE organization_id = '...' AND match_id = '...';
```

### PostgreSQL Sharding (Citus) / Шардинг PostgreSQL (Citus)

```sql
-- Citus extension for PostgreSQL sharding

-- 1. Create distributed table
CREATE TABLE matches (
    id UUID PRIMARY KEY,
    organization_id UUID NOT NULL,
    home_team TEXT,
    away_team TEXT,
    created_at TIMESTAMPTZ
);

-- 2. Distribute by organization_id
SELECT create_distributed_table('matches', 'organization_id');

-- 3. Queries are automatically routed
SELECT * FROM matches WHERE organization_id = '...';

-- 4. Cross-shard queries work but are slower
SELECT organization_id, count(*)
FROM matches
GROUP BY organization_id;  -- Needs data from all shards
```

---

## Resharding Strategies / Стратегии решардинга

```
┌─────────────────────────────────────────────────────────────────────┐
│                      RESHARDING STRATEGIES                           │
│                                                                      │
│  When to reshard:                                                   │
│  • Shard capacity exceeded                                          │
│  • Hot spots (uneven load)                                          │
│  • Adding/removing nodes                                            │
│                                                                      │
│  STRATEGY 1: DOUBLE WRITES                                          │
│  ───────────────────────────────────────────────────────────────── │
│                                                                      │
│  1. Create new shard configuration                                  │
│  2. Write to BOTH old and new shards                                │
│  3. Migrate historical data in background                           │
│  4. Switch reads to new shards                                      │
│  5. Stop writes to old shards                                       │
│                                                                      │
│  Pros: Zero downtime                                                │
│  Cons: Temporary 2x write load, complexity                          │
│                                                                      │
│  STRATEGY 2: SHARD SPLIT                                            │
│  ───────────────────────────────────────────────────────────────── │
│                                                                      │
│  Before:  [Shard 1: A-M]  [Shard 2: N-Z]                           │
│  After:   [Shard 1: A-G] [Shard 3: H-M] [Shard 2: N-Z]             │
│                                                                      │
│  1. Create new shard (Shard 3)                                      │
│  2. Copy H-M data from Shard 1 to Shard 3                          │
│  3. Update routing to send H-M to Shard 3                          │
│  4. Delete H-M from Shard 1                                        │
│                                                                      │
│  STRATEGY 3: CONSISTENT HASHING (Automatic)                         │
│  ───────────────────────────────────────────────────────────────── │
│                                                                      │
│  Add new node to ring → only ~1/N data migrates                    │
│  Used by: Cassandra, DynamoDB, Riak                                 │
│  Minimal manual intervention                                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Interview Questions / Вопросы для интервью

**Q1: What is the difference between replication and sharding?**

A: Replication copies the same data to multiple nodes for availability and read scaling - each replica has a complete copy. Sharding splits data across nodes - each shard has a subset. Replication alone doesn't help with write scaling (all writes go to primary). Sharding distributes writes but doesn't provide redundancy alone. Production systems use both: shards for horizontal scaling, replicas per shard for availability.

**Q2: Explain consistent hashing and why it's used.**

A: Consistent hashing maps both data keys and nodes to a circular hash space (ring). Keys are assigned to the first node clockwise from their position. When adding/removing nodes, only ~1/N keys need to move (N = number of nodes). This is much better than simple modulo hashing where changing N causes ~(N-1)/N keys to move. Virtual nodes (multiple positions per physical node) improve distribution. Used in Cassandra, DynamoDB, CDNs.

**Q3: How would you choose a shard key for a multi-tenant SaaS application?**

A: For multi-tenant SaaS, the primary shard key candidate is `tenant_id` or `organization_id`: (1) Provides natural data isolation - one tenant's data on one shard, (2) Queries almost always filter by tenant (required for security), (3) High cardinality if many tenants, (4) Immutable - tenants don't change IDs. Risks: Large tenants may overload their shard (hot spot). Mitigations: Dedicated shards for large tenants, or compound key like `(tenant_id, hash(entity_id))` to spread large tenants across shards.

---

## Связано с

- [[SQL-vs-NoSQL]]
- [[Consensus]]

## Ресурсы

- [Designing Data-Intensive Applications - Martin Kleppmann](https://dataintensive.net/)
- [Consistent Hashing Paper (Karger et al.)](https://www.cs.princeton.edu/courses/archive/fall09/cos518/papers/chash.pdf)
- [ClickHouse Distributed Tables](https://clickhouse.com/docs/en/engines/table-engines/special/distributed)
- [PostgreSQL Citus Extension](https://docs.citusdata.com/)
- [Cassandra Architecture](https://cassandra.apache.org/doc/latest/cassandra/architecture/)
- [Amazon DynamoDB Paper](https://www.allthingsdistributed.com/files/amazon-dynamo-sosp2007.pdf)

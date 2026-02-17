---
tags:
  - system-design
  - databases
  - sql
  - nosql
created: 2026-02-17
---

# SQL vs NoSQL: Database Selection Guide
# SQL vs NoSQL: Руководство по выбору базы данных

> **Reading time:** ~15 min | **Время чтения:** ~15 мин

## Что это

Руководство по выбору между SQL и NoSQL базами данных: теорема CAP, ACID vs BASE, категории NoSQL (Document, Key-Value, Wide-Column, Graph), фреймворк принятия решений, полиглотная персистенция.

Choosing between SQL and NoSQL databases is one of the most impactful architectural decisions in any system. This document covers the theoretical foundations, practical tradeoffs, and decision frameworks for database selection.

Выбор между SQL и NoSQL базами данных — одно из самых важных архитектурных решений. Этот документ рассматривает теоретические основы, практические компромиссы и фреймворки принятия решений.

---

## The CAP Theorem / Теорема CAP

### Definition / Определение

The CAP theorem, formulated by Eric Brewer in 2000, states that a distributed data store can only provide **two out of three** guarantees:

Теорема CAP, сформулированная Эриком Брюэром в 2000 году, утверждает, что распределённое хранилище данных может обеспечить только **две из трёх** гарантий:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CAP THEOREM                                  │
│                                                                      │
│                           Consistency                                │
│                              /\                                      │
│                             /  \                                     │
│                            /    \                                    │
│                           /  CA  \                                   │
│                          /        \                                  │
│                         /          \                                 │
│                        /            \                                │
│                       /______________\                               │
│                      /                \                              │
│                     / CP            AP \                             │
│                    /                    \                            │
│              Partition              Availability                     │
│              Tolerance                                               │
│                                                                      │
│  You can only choose TWO:                                           │
│  • CA: Consistent + Available (no partition tolerance)              │
│  • CP: Consistent + Partition-tolerant (sacrifices availability)    │
│  • AP: Available + Partition-tolerant (sacrifices consistency)      │
└─────────────────────────────────────────────────────────────────────┘
```

### The Three Guarantees / Три гарантии

| Property | Definition (EN) | Определение (RU) |
|----------|-----------------|------------------|
| **Consistency** | Every read receives the most recent write | Каждое чтение получает самую последнюю запись |
| **Availability** | Every request receives a response (not error) | Каждый запрос получает ответ (не ошибку) |
| **Partition Tolerance** | System continues despite network failures | Система продолжает работать при сетевых сбоях |

### Why You Must Choose Partition Tolerance / Почему нужно выбирать устойчивость к разделению

In distributed systems, network partitions **will** happen. Therefore, practical systems must choose between CP and AP:

В распределённых системах сетевые разделения **будут** происходить. Поэтому практические системы должны выбирать между CP и AP:

```
┌─────────────────────────────────────────────────────────────────────┐
│  NETWORK PARTITION SCENARIO                                          │
│                                                                      │
│  ┌─────────────┐          PARTITION          ┌─────────────┐        │
│  │   Node A    │ ═════════════╳══════════════│   Node B    │        │
│  │             │        (network down)        │             │        │
│  │  Data: X=1  │                              │  Data: X=1  │        │
│  └─────────────┘                              └─────────────┘        │
│                                                                      │
│  Client writes X=2 to Node A:                                       │
│                                                                      │
│  CP System (e.g., PostgreSQL cluster):                              │
│  • Node A rejects write (cannot sync with B)                        │
│  • Maintains consistency, sacrifices availability                   │
│                                                                      │
│  AP System (e.g., Cassandra):                                       │
│  • Node A accepts write (X=2)                                       │
│  • Node B still has X=1                                             │
│  • Maintains availability, sacrifices consistency                   │
│  • Later: reconciliation needed                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Real-World CAP Classifications / Классификации CAP в реальных системах

| System | CAP | Notes |
|--------|-----|-------|
| PostgreSQL (single) | CA | No partition tolerance (single node) |
| PostgreSQL + Patroni | CP | Sacrifices availability during failover |
| MySQL + Galera | CP | All nodes must agree on writes |
| MongoDB | CP* | Configurable, prefers consistency |
| Cassandra | AP | Eventual consistency, high availability |
| CockroachDB | CP | Distributed SQL with strong consistency |
| DynamoDB | AP* | Configurable consistency levels |
| [[Redis-Patterns\|Redis]] Cluster | AP | Eventual consistency, async replication |

*Configurable: Can adjust behavior based on use case

---

## ACID vs BASE / ACID против BASE

### ACID Properties / Свойства ACID

Traditional relational databases follow ACID properties for transactions:

Традиционные реляционные базы данных следуют свойствам ACID для транзакций:

```
┌─────────────────────────────────────────────────────────────────────┐
│                          ACID PROPERTIES                             │
│                                                                      │
│  A - Atomicity (Атомарность)                                        │
│  ────────────────────────────────────────────────────────────────   │
│  Transaction is "all or nothing"                                    │
│  Транзакция — "всё или ничего"                                      │
│                                                                      │
│  Example:                                                           │
│  BEGIN TRANSACTION;                                                 │
│    UPDATE accounts SET balance = balance - 100 WHERE id = 1;        │
│    UPDATE accounts SET balance = balance + 100 WHERE id = 2;        │
│  COMMIT;  -- Either BOTH happen, or NEITHER                        │
│                                                                      │
│  C - Consistency (Согласованность)                                  │
│  ────────────────────────────────────────────────────────────────   │
│  Database moves from one valid state to another                     │
│  База данных переходит из одного валидного состояния в другое       │
│                                                                      │
│  Example: Constraints, triggers, foreign keys enforced              │
│                                                                      │
│  I - Isolation (Изоляция)                                           │
│  ────────────────────────────────────────────────────────────────   │
│  Concurrent transactions don't interfere                            │
│  Параллельные транзакции не мешают друг другу                       │
│                                                                      │
│  Isolation Levels:                                                  │
│  • READ UNCOMMITTED (dirty reads possible)                          │
│  • READ COMMITTED (default in PostgreSQL)                           │
│  • REPEATABLE READ (default in MySQL InnoDB)                        │
│  • SERIALIZABLE (strongest, slowest)                                │
│                                                                      │
│  D - Durability (Долговечность)                                     │
│  ────────────────────────────────────────────────────────────────   │
│  Committed transactions survive crashes                             │
│  Подтверждённые транзакции переживают сбои                          │
│                                                                      │
│  Implementation: Write-ahead log (WAL), fsync                       │
└─────────────────────────────────────────────────────────────────────┘
```

### BASE Properties / Свойства BASE

NoSQL databases often follow BASE (Basically Available, Soft state, Eventually consistent):

NoSQL базы данных часто следуют BASE (Базовая доступность, Мягкое состояние, Согласованность в конечном счёте):

```
┌─────────────────────────────────────────────────────────────────────┐
│                          BASE PROPERTIES                             │
│                                                                      │
│  BA - Basically Available (Базовая доступность)                     │
│  ────────────────────────────────────────────────────────────────   │
│  System guarantees availability (even if stale data)                │
│  Система гарантирует доступность (даже если данные устарели)        │
│                                                                      │
│  S - Soft State (Мягкое состояние)                                  │
│  ────────────────────────────────────────────────────────────────   │
│  State may change over time due to eventual consistency             │
│  Состояние может меняться со временем из-за согласованности         │
│                                                                      │
│  E - Eventually Consistent (Согласованность в конечном счёте)       │
│  ────────────────────────────────────────────────────────────────   │
│  System will become consistent given enough time                    │
│  Система станет согласованной при достаточном времени               │
│                                                                      │
│  Example flow:                                                      │
│  T=0:  Write X=2 to Node A                                          │
│  T=1:  Read X from Node B → returns X=1 (stale!)                   │
│  T=2:  Background sync: A → B                                       │
│  T=3:  Read X from Node B → returns X=2 (consistent!)              │
└─────────────────────────────────────────────────────────────────────┘
```

### ACID vs BASE Comparison / Сравнение ACID и BASE

| Aspect | ACID | BASE |
|--------|------|------|
| **Consistency model** | Strong | Eventual |
| **Focus** | Correctness | Availability |
| **Scalability** | Vertical (mostly) | Horizontal |
| **Latency** | Higher (coordination) | Lower (no coordination) |
| **Use cases** | Banking, inventory | Social feeds, analytics |
| **Conflict handling** | Locks/MVCC | Last-write-wins, CRDTs |
| **Complexity** | In database | In application |

---

## SQL Databases / SQL Базы данных

### Characteristics / Характеристики

```
┌─────────────────────────────────────────────────────────────────────┐
│                      SQL DATABASE CHARACTERISTICS                    │
│                                                                      │
│  1. STRUCTURED DATA                                                 │
│     • Fixed schema defined upfront                                  │
│     • Tables, rows, columns                                         │
│     • Data types enforced                                           │
│                                                                      │
│  2. RELATIONSHIPS                                                   │
│     • Foreign keys                                                  │
│     • JOINs across tables                                           │
│     • Referential integrity                                         │
│                                                                      │
│  3. QUERY LANGUAGE                                                  │
│     • Declarative SQL                                               │
│     • Complex queries, aggregations                                 │
│     • Query optimizer                                               │
│                                                                      │
│  4. TRANSACTIONS                                                    │
│     • ACID guarantees                                               │
│     • Multi-statement transactions                                  │
│     • Rollback on failure                                           │
└─────────────────────────────────────────────────────────────────────┘
```

### Major SQL Databases / Основные SQL базы данных

| Database | Strengths | Best For |
|----------|-----------|----------|
| **PostgreSQL** | Extensions, JSON support, ACID | General purpose, geospatial |
| **MySQL** | Read performance, replication | Web apps, read-heavy workloads |
| **SQLite** | Embedded, zero-config | Mobile apps, testing, edge |
| **SQL Server** | Enterprise features, BI | Microsoft ecosystem |
| **Oracle** | Extreme scale, features | Large enterprises |
| **CockroachDB** | Distributed SQL, CP | Global apps needing SQL |

### SQL Example: Relational Model / SQL Пример: Реляционная модель

```sql
-- Normalized relational schema
CREATE TABLE organizations (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255)
);

CREATE TABLE memberships (
    user_id UUID REFERENCES users(id),
    org_id UUID REFERENCES organizations(id),
    role VARCHAR(50) NOT NULL,
    PRIMARY KEY (user_id, org_id)
);

-- Query with JOIN
SELECT u.name, o.name as org_name, m.role
FROM users u
JOIN memberships m ON u.id = m.user_id
JOIN organizations o ON o.id = m.org_id
WHERE u.email = 'user@example.com';
```

---

## NoSQL Databases / NoSQL Базы данных

### Categories / Категории

```
┌─────────────────────────────────────────────────────────────────────┐
│                     NoSQL DATABASE CATEGORIES                        │
│                                                                      │
│  1. DOCUMENT STORES                                                 │
│     ┌───────────────────────────────────────────────────────────┐   │
│     │ { "_id": "123", "name": "Match", "teams": [...] }         │   │
│     └───────────────────────────────────────────────────────────┘   │
│     Examples: MongoDB, Couchbase, Firebase                          │
│     Best for: Variable schema, nested data, content management     │
│                                                                      │
│  2. KEY-VALUE STORES                                                │
│     ┌────────────────────────┐                                      │
│     │ key: "session:abc123"  │                                      │
│     │ value: {binary blob}   │                                      │
│     └────────────────────────┘                                      │
│     Examples: Redis, Memcached, DynamoDB                            │
│     Best for: Caching, sessions, simple lookups                     │
│                                                                      │
│  3. WIDE-COLUMN STORES                                              │
│     ┌──────────────────────────────────────────────────────┐        │
│     │ Row key │ Column family: info    │ Column family: stats │    │
│     │ user:1  │ name="John" age=30     │ logins=100           │    │
│     └──────────────────────────────────────────────────────┘        │
│     Examples: Cassandra, HBase, ScyllaDB                            │
│     Best for: Time series, high write throughput, wide rows         │
│                                                                      │
│  4. GRAPH DATABASES                                                 │
│     ┌────────────────────────────────────────────┐                  │
│     │   (User)──[FOLLOWS]──>(User)               │                  │
│     │     │                                       │                  │
│     │   [POSTED]                                  │                  │
│     │     │                                       │                  │
│     │     v                                       │                  │
│     │   (Post)                                    │                  │
│     └────────────────────────────────────────────┘                  │
│     Examples: Neo4j, Amazon Neptune, ArangoDB                       │
│     Best for: Social networks, recommendations, fraud detection    │
└─────────────────────────────────────────────────────────────────────┘
```

### NoSQL Example: Document Store / NoSQL Пример: Документная база

```javascript
// MongoDB document - denormalized for read performance
{
  "_id": "match_001",
  "scheduled_at": ISODate("2026-01-15T15:00:00Z"),
  "home_team": {
    "id": "team_001",
    "name": "FC Barcelona",
    "logo_url": "..."
  },
  "away_team": {
    "id": "team_002",
    "name": "Real Madrid",
    "logo_url": "..."
  },
  "venue": {
    "id": "venue_001",
    "name": "Camp Nou",
    "capacity": 99354
  },
  "status": "completed",
  "score": { "home": 2, "away": 1 }
}

// Single query retrieves all data (no JOINs)
db.matches.findOne({ "_id": "match_001" })
```

---

## Decision Framework / Фреймворк принятия решений

### When to Choose SQL / Когда выбирать SQL

```
┌─────────────────────────────────────────────────────────────────────┐
│  CHOOSE SQL WHEN:                                                    │
│                                                                      │
│  ✓ Complex relationships between entities                           │
│  ✓ Need ACID transactions across multiple tables                    │
│  ✓ Schema is well-defined and stable                                │
│  ✓ Complex queries with JOINs, aggregations                         │
│  ✓ Strong consistency is required                                   │
│  ✓ Team has SQL expertise                                           │
│                                                                      │
│  EXAMPLES:                                                          │
│  • E-commerce orders and inventory                                  │
│  • Financial transactions                                           │
│  • User management and authentication                               │
│  • CRM systems                                                       │
│  • ERP systems                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### When to Choose NoSQL / Когда выбирать NoSQL

```
┌─────────────────────────────────────────────────────────────────────┐
│  CHOOSE NoSQL WHEN:                                                  │
│                                                                      │
│  ✓ Schema varies or evolves frequently                              │
│  ✓ Need horizontal scalability                                      │
│  ✓ High write throughput required                                   │
│  ✓ Eventual consistency is acceptable                               │
│  ✓ Data is naturally hierarchical/nested                            │
│  ✓ Simple access patterns (key lookup)                              │
│                                                                      │
│  EXAMPLES:                                                          │
│  • User session data (Redis)                                        │
│  • Product catalogs with varying attributes (MongoDB)               │
│  • Time series data (Cassandra, ClickHouse)                         │
│  • Social media feeds (Cassandra)                                   │
│  • Real-time analytics (ClickHouse)                                 │
│  • IoT sensor data (InfluxDB)                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### Decision Matrix / Матрица решений

| Requirement | SQL | Document | Key-Value | Column | Graph |
|-------------|-----|----------|-----------|--------|-------|
| Complex JOINs | Best | Poor | N/A | Poor | Good |
| Flexible schema | Poor | Best | Good | Good | Good |
| Horizontal scale | Hard | Easy | Easy | Easy | Medium |
| ACID transactions | Best | Medium | Poor | Poor | Good |
| High write speed | Medium | Good | Best | Best | Medium |
| Caching | Poor | Poor | Best | Poor | Poor |
| Relationships | Good | Poor | Poor | Poor | Best |
| Time series | Medium | Poor | Poor | Best | Poor |

---

## Polyglot Persistence / Полиглотная персистенция

Modern systems often use multiple databases, each optimized for specific use cases:

Современные системы часто используют несколько баз данных, каждая оптимизирована для конкретных случаев:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    POLYGLOT PERSISTENCE EXAMPLE                      │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                       APPLICATION                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│         │              │              │              │              │
│         ▼              ▼              ▼              ▼              │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐        │
│  │PostgreSQL │  │ ClickHouse│  │   Redis   │  │   MinIO   │        │
│  │           │  │           │  │           │  │           │        │
│  │ Metadata  │  │ Time      │  │ Cache     │  │ Binary    │        │
│  │ Users     │  │ Series    │  │ Sessions  │  │ Objects   │        │
│  │ Matches   │  │ Detections│  │ API Cache │  │ Videos    │        │
│  │ Relations │  │ Analytics │  │ Pub/Sub   │  │ Artifacts │        │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘        │
│                                                                      │
│  Each database chosen for its strengths:                            │
│  • PostgreSQL: ACID, relationships, complex queries                 │
│  • ClickHouse: Analytical queries on millions of rows               │
│  • Redis: Sub-millisecond access, ephemeral data                    │
│  • MinIO: Large binary objects (S3-compatible)                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Interview Questions / Вопросы для интервью

**Q1: Explain the CAP theorem and why you can't have all three.**

A: The CAP theorem states that in a distributed system, you can only guarantee two of three properties: Consistency, Availability, and Partition Tolerance. Since network partitions are inevitable in distributed systems, the real choice is between CP (consistent but may be unavailable during partitions) and AP (always available but may return stale data). You can't have all three because during a network partition, a node must either reject requests to stay consistent (CP) or accept requests knowing it might diverge from other nodes (AP).

**Q2: When would you choose eventual consistency over strong consistency?**

A: Eventual consistency is appropriate when: (1) The application can tolerate stale reads for a short time, (2) High availability is more important than immediate consistency, (3) The system needs to scale horizontally across regions, (4) Conflicts can be resolved automatically (last-write-wins, CRDTs). Examples include social media feeds, product views, analytics dashboards. Strong consistency is required for financial transactions, inventory management, or any case where incorrect data causes serious problems.

**Q3: What is the difference between SQL and NoSQL database scaling approaches?**

A: SQL databases traditionally scale vertically (bigger hardware) because maintaining ACID across distributed nodes is complex. Modern distributed SQL (CockroachDB, Spanner) exists but adds latency. NoSQL databases are designed for horizontal scaling (more nodes) by relaxing consistency guarantees. They use techniques like sharding, eventual consistency, and conflict resolution. The tradeoff is that SQL makes application code simpler (database handles consistency) while NoSQL requires application code to handle consistency (more complex but more scalable).

## Связано с

- [[TimeSeries-DB]]
- [[Sharding]]
- [[Redis-Patterns]]

## Ресурсы

- [Brewer's CAP Theorem (Original Paper)](https://www.cs.berkeley.edu/~brewer/cs262b-2004/PODC-keynote.pdf)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [MongoDB vs PostgreSQL Comparison](https://www.mongodb.com/compare/mongodb-postgresql)
- [Designing Data-Intensive Applications - Martin Kleppmann](https://dataintensive.net/)
- [CAP Twelve Years Later](https://www.infoq.com/articles/cap-twelve-years-later-how-the-rules-have-changed/)

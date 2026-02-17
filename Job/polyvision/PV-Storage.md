---
tags:
  - polyvision
  - system-design
  - databases
  - clickhouse
  - redis
created: 2026-02-17
---

## Что это

Анализ архитектурных решений по хранению данных для платформы Polyvision: выбор ClickHouse для временных рядов детекции (ADR-021), дизайн с двумя Redis-инстансами, PostgreSQL для метаданных и MinIO/Ceph для бинарных объектов.

---

# Polyvision Data Storage Decision: ADR-021 Analysis
# Решение по хранению данных Polyvision: Анализ ADR-021

> **Context:** This document analyzes the data storage architecture decisions for the Polyvision sports analytics platform, including the ClickHouse time series decision (ADR-021), dual Redis design, and polyglot persistence strategy.
>
> **Контекст:** Этот документ анализирует архитектурные решения по хранению данных для платформы спортивной аналитики Polyvision, включая решение по ClickHouse (ADR-021), дизайн с двумя Redis и стратегию полиглотной персистенции.

---

## Problem Statement / Постановка задачи

Polyvision processes football match footage and generates detection data at massive scale:

Polyvision обрабатывает видеозаписи футбольных матчей и генерирует данные детекции в огромных масштабах:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      DATA VOLUME ANALYSIS                            │
│                                                                      │
│  Per 90-minute match:                                               │
│  ─────────────────────────────────────────────────────────────────  │
│  • Duration: 90 minutes = 5,400 seconds                             │
│  • Frame rate: 60 FPS                                               │
│  • Total frames: 324,000 frames/match                               │
│  • Avg detections per frame: ~14 (ball + 22 players + refs)         │
│  • Total detections: ~4.5 million records/match                     │
│                                                                      │
│  Per detection record (~100 bytes):                                 │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │ organization_id: UUID (16 bytes)                            │     │
│  │ match_id: UUID (16 bytes)                                   │     │
│  │ frame_idx: UInt32 (4 bytes)                                 │     │
│  │ pts, wallclock_ns: Int64 (16 bytes)                         │     │
│  │ class_id, tile_id: UInt8 (2 bytes)                          │     │
│  │ confidence: Float32 (4 bytes)                               │     │
│  │ x, y, width, height: Float32 (16 bytes)                     │     │
│  │ track_id: Nullable UInt32 (5 bytes)                         │     │
│  │ model_version: String (~20 bytes)                           │     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                      │
│  Storage requirements:                                               │
│  • Raw: ~450 MB/match (4.5M × 100 bytes)                           │
│  • Compressed (ClickHouse): ~45-80 MB/match (10x compression)       │
│  • Annual (100 matches/week): ~400 GB compressed                    │
│                                                                      │
│  Query patterns:                                                     │
│  • Time-range queries (ball position in minute 45-50)               │
│  • Aggregations (heatmaps, player stats)                            │
│  • Per-match analytics (all data for one match)                     │
│  • Cross-match analytics (season-level stats)                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Storage Architecture Overview / Обзор архитектуры хранения

Polyvision uses polyglot persistence - multiple specialized databases for different data types:

Polyvision использует полиглотную персистенцию - несколько специализированных баз данных для разных типов данных:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    POLYVISION DATA ARCHITECTURE                      │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                     APPLICATION LAYER                        │    │
│  └─────────────────────────────────────────────────────────────┘    │
│         │              │              │              │               │
│         ▼              ▼              ▼              ▼               │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐         │
│  │PostgreSQL │  │ ClickHouse│  │redis-cache│  │redis-celery│        │
│  │           │  │           │  │           │  │           │         │
│  │ Metadata  │  │ Time      │  │ API Cache │  │ Task      │         │
│  │ Users     │  │ Series    │  │ Sessions  │  │ Broker    │         │
│  │ Matches   │  │ Detections│  │ Hot data  │  │ Results   │         │
│  │ Jobs      │  │ Heatmaps  │  │           │  │           │         │
│  │           │  │ Analytics │  │ allkeys-  │  │ noeviction│         │
│  │ ACID      │  │           │  │ lru       │  │           │         │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘         │
│         │              │              │              │               │
│         │              │              │              │               │
│         │              └───────┬──────┘              │               │
│         │                      │                     │               │
│         │                      ▼                     │               │
│         │            ┌─────────────────┐            │               │
│         └───────────►│      MinIO      │◄───────────┘               │
│                      │  (S3-compatible) │                            │
│                      │                 │                            │
│                      │ • Raw videos    │                            │
│                      │ • Panoramas     │                            │
│                      │ • HLS segments  │                            │
│                      │ • Parquet archive│                           │
│                      │ • Calibrations  │                            │
│                      └─────────────────┘                            │
│                                                                      │
│  Data flow:                                                         │
│  1. Detect Worker → INSERT → ClickHouse (primary)                   │
│  2. PostgreSQL stores match metadata, job state                     │
│  3. Redis caches hot queries, manages Celery tasks                  │
│  4. MinIO stores large binary objects                               │
│  5. Weekly: ClickHouse → Parquet → MinIO (archive)                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Decision 1: ClickHouse for Detection Time Series (ADR-021)
## Решение 1: ClickHouse для временных рядов детекции

### Why ClickHouse? / Почему ClickHouse?

```
┌─────────────────────────────────────────────────────────────────────┐
│               ALTERNATIVES CONSIDERED (ADR-021)                      │
│                                                                      │
│  OPTION A: PostgreSQL (with partitioning)                           │
│  ─────────────────────────────────────────────────────────────────  │
│  Pros:                                                              │
│  • Already in stack (metadata DB)                                   │
│  • Full SQL, ACID transactions                                      │
│  • Team familiarity                                                 │
│                                                                      │
│  Cons:                                                              │
│  ✗ Row-based storage inefficient for analytical scans              │
│  ✗ 4.5M rows/match = slow aggregation queries                      │
│  ✗ Poor compression for time series                                │
│  ✗ Vacuum overhead with high INSERT rate                           │
│                                                                      │
│  Verdict: Not suitable for analytical workload                      │
│                                                                      │
│  ─────────────────────────────────────────────────────────────────  │
│  OPTION B: TimescaleDB                                              │
│  ─────────────────────────────────────────────────────────────────  │
│  Pros:                                                              │
│  • PostgreSQL extension (familiar SQL)                              │
│  • Automatic time-based partitioning (hypertables)                  │
│  • Good compression for older data                                  │
│  • JOINs with metadata in same DB                                   │
│                                                                      │
│  Cons:                                                              │
│  ✗ Slower than ClickHouse for large aggregations                   │
│  ✗ Single-node limits without Timescale Cloud                      │
│  ✗ Still row-based under the hood                                  │
│                                                                      │
│  Verdict: Viable but not optimal for our scale                      │
│                                                                      │
│  ─────────────────────────────────────────────────────────────────  │
│  OPTION C: InfluxDB                                                 │
│  ─────────────────────────────────────────────────────────────────  │
│  Pros:                                                              │
│  • Purpose-built for time series                                    │
│  • Excellent for metrics (float values)                             │
│                                                                      │
│  Cons:                                                              │
│  ✗ Designed for metrics, not event data with complex structure     │
│  ✗ Bounding boxes (x, y, width, height) awkward to model          │
│  ✗ Flux query language learning curve                              │
│  ✗ Limited JOIN capabilities                                       │
│                                                                      │
│  Verdict: Wrong data model for detection records                    │
│                                                                      │
│  ─────────────────────────────────────────────────────────────────  │
│  OPTION D: ClickHouse -- CHOSEN                                     │
│  ─────────────────────────────────────────────────────────────────  │
│  Pros:                                                              │
│  + Columnar storage: 10-40x compression                             │
│  + Vectorized queries: billions of rows/second                      │
│  + SQL interface (familiar)                                         │
│  + Materialized views for auto-computed aggregations                │
│  + Time-based TTL for data lifecycle                                │
│  + Partitioning by time for efficient cleanup                       │
│                                                                      │
│  Cons:                                                              │
│  • Additional infrastructure component                              │
│  • Learning ClickHouse-specific SQL extensions                     │
│  • No ACID (insert-only, eventual consistency for MVs)             │
│                                                                      │
│  Verdict: Best fit for analytical time series workload              │
└─────────────────────────────────────────────────────────────────────┘
```

### ClickHouse Schema Design / Дизайн схемы ClickHouse

```sql
-- Polyvision detection schema (production-ready)

CREATE TABLE detections (
    -- Tenant isolation (REQUIRED for multi-tenancy)
    organization_id UUID,

    -- Keys
    match_id UUID,
    frame_idx UInt32,

    -- Timestamps
    pts Int64,                           -- Presentation timestamp
    wallclock_ns Int64,                  -- Wall clock (UTC nanoseconds)
    created_at DateTime DEFAULT now(),  -- Required for TTL

    -- Detection data
    class_id UInt8,                      -- 0=ball, 1=player, etc.
    confidence Float32,
    x Float32, y Float32,                -- Bounding box center
    width Float32, height Float32,       -- Bounding box size
    tile_id UInt8,                       -- Source tile (0-17)

    -- Tracking (populated after tracking pass)
    track_id Nullable(UInt32),

    -- Provenance
    model_version LowCardinality(String),
    pass_number UInt8 DEFAULT 1
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)       -- Time-based partitioning
ORDER BY (organization_id, match_id, frame_idx, class_id)
TTL created_at + INTERVAL 90 DAY DELETE -- Auto-cleanup
SETTINGS ttl_only_drop_parts = 1, merge_with_ttl_timeout = 3600;
```

### Partitioning Decision / Решение по партиционированию

```
┌─────────────────────────────────────────────────────────────────────┐
│              PARTITIONING STRATEGY ANALYSIS                          │
│                                                                      │
│  OPTION A: Partition by match_id                                    │
│  ─────────────────────────────────────────────────────────────────  │
│  PARTITION BY match_id                                              │
│                                                                      │
│  Pros:                                                              │
│  • One partition per match (easy cleanup)                           │
│  • Efficient per-match queries                                      │
│                                                                      │
│  Cons:                                                              │
│  ✗ High cardinality: 1000s of partitions/year                      │
│  ✗ ClickHouse limit: ~1000 active partitions recommended           │
│  ✗ Metadata overhead per partition                                  │
│  ✗ TTL cannot drop whole partitions efficiently                    │
│                                                                      │
│  Verdict: Partition explosion problem                               │
│                                                                      │
│  ─────────────────────────────────────────────────────────────────  │
│  OPTION B: Partition by toYYYYMM(created_at) -- CHOSEN              │
│  ─────────────────────────────────────────────────────────────────  │
│  PARTITION BY toYYYYMM(created_at)                                  │
│                                                                      │
│  Pros:                                                              │
│  + Max 12 partitions/year (bounded growth)                          │
│  + TTL can drop whole partitions (efficient)                        │
│  + Follows ClickHouse best practices                                │
│  + Time-range queries efficient                                     │
│                                                                      │
│  Cons:                                                              │
│  • Per-match queries scan more data                                 │
│    (mitigated by ORDER BY org_id, match_id)                        │
│                                                                      │
│  Verdict: Correct choice for production                             │
└─────────────────────────────────────────────────────────────────────┘
```

### Materialized Views / Материализованные представления

```sql
-- Auto-computed heatmaps (SummingMergeTree)
CREATE MATERIALIZED VIEW heatmap_grid_mv
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(created_at)
ORDER BY (organization_id, match_id, class_id, grid_x, grid_y)
AS SELECT
    organization_id, match_id, class_id,
    intDiv(toUInt32(x), 100) AS grid_x,
    intDiv(toUInt32(y), 100) AS grid_y,
    count() AS presence_count,
    max(created_at) AS created_at
FROM detections
GROUP BY organization_id, match_id, class_id, grid_x, grid_y;

-- Ball position timeline (ReplacingMergeTree for dedup)
CREATE MATERIALIZED VIEW ball_timeline_mv
ENGINE = ReplacingMergeTree(created_at)
PARTITION BY toYYYYMM(created_at)
ORDER BY (organization_id, match_id, frame_idx)
AS SELECT
    organization_id, match_id, frame_idx,
    argMax(x, confidence) AS ball_x,
    argMax(y, confidence) AS ball_y,
    max(confidence) AS confidence,
    max(created_at) AS created_at
FROM detections
WHERE class_id = 0  -- ball only
GROUP BY organization_id, match_id, frame_idx;
```

---

## Decision 2: Dual Redis Architecture
## Решение 2: Архитектура с двумя Redis

### Why Two Redis Instances? / Почему два экземпляра Redis?

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DUAL REDIS ARCHITECTURE                           │
│                                                                      │
│  THE PROBLEM: Single Redis with conflicting requirements            │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                      │
│  Caching needs:                    Celery broker needs:             │
│  • Can lose data (it's a cache)    • NEVER lose tasks              │
│  • Evict when full (LRU)           • Error when full (backpressure)│
│  • High memory turnover            • Stable memory usage           │
│                                                                      │
│  These are INCOMPATIBLE in one instance!                            │
│                                                                      │
│  ─────────────────────────────────────────────────────────────────  │
│  THE SOLUTION: Separate instances with different policies           │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                      │
│  ┌─────────────────────────┐     ┌─────────────────────────┐        │
│  │      redis-cache        │     │     redis-celery        │        │
│  │      Port: 6379         │     │      Port: 6380         │        │
│  │                         │     │                         │        │
│  │  maxmemory: 4GB         │     │  maxmemory: 2GB         │        │
│  │  policy: allkeys-lru    │     │  policy: noeviction     │        │
│  │                         │     │                         │        │
│  │  Usage:                 │     │  Usage:                 │        │
│  │  • API response cache   │     │  • Celery broker        │        │
│  │  • Session storage      │     │  • Task results         │        │
│  │  • Hot analytics data   │     │  • Idempotency keys     │        │
│  │  • Idempotency checks   │     │                         │        │
│  │                         │     │                         │        │
│  │  If full:               │     │  If full:               │        │
│  │  → Evict LRU keys       │     │  → REJECT writes        │        │
│  │  → Cache miss = slow    │     │  → Alert operators      │        │
│  │    query (acceptable)   │     │  → No task loss         │        │
│  └─────────────────────────┘     └─────────────────────────┘        │
│                                                                      │
│  Critical insight:                                                  │
│  • Cache eviction = performance degradation (acceptable)            │
│  • Task eviction = data loss (UNACCEPTABLE)                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Redis Configuration / Конфигурация Redis

```bash
# redis-cache.conf
# For API caching, sessions, hot data

maxmemory 4gb
maxmemory-policy allkeys-lru   # Evict least recently used
maxmemory-samples 10           # LRU approximation accuracy

# Persistence: optional (cache can rebuild)
save ""                        # Disable RDB snapshots
appendonly no                  # Disable AOF

# Performance
tcp-keepalive 300
timeout 0
```

```bash
# redis-celery.conf
# For Celery task broker

maxmemory 2gb
maxmemory-policy noeviction    # CRITICAL: never lose tasks!

# Persistence: enabled (protect tasks)
appendonly yes
appendfsync everysec           # Sync AOF every second

# Alert if near limit
# (external monitoring required)
```

### Celery Configuration / Конфигурация Celery

```python
# celeryconfig.py

# Use dedicated Redis for broker
broker_url = "redis://redis-celery:6380/0"

# Results can use cache Redis (less critical)
result_backend = "redis://redis-cache:6379/1"

# CRITICAL: Safe acknowledgment
task_acks_late = True              # ACK after completion
task_reject_on_worker_lost = True  # Requeue if worker dies
worker_prefetch_multiplier = 1     # Don't prefetch (lose on crash)

# Task-level settings
task_default_retry_delay = 60
task_max_retries = 3
```

---

## Decision 3: PostgreSQL for Metadata
## Решение 3: PostgreSQL для метаданных

### What Goes in PostgreSQL? / Что хранится в PostgreSQL?

```
┌─────────────────────────────────────────────────────────────────────┐
│                POSTGRESQL METADATA STORAGE                           │
│                                                                      │
│  PostgreSQL is the ACID-compliant source of truth for:              │
│                                                                      │
│  ENTITIES & RELATIONSHIPS                                           │
│  ─────────────────────────────────────────────────────────────────  │
│  • organizations (multi-tenant root)                                │
│  • users, organization_memberships                                  │
│  • venues, camera_rigs                                              │
│  • calibration_versions (version control for LUTs)                  │
│  • matches (core entity)                                            │
│  • detection_datasets (metadata, not actual detections)             │
│  • subscriptions (billing)                                          │
│                                                                      │
│  JOB STATE & COORDINATION                                           │
│  ─────────────────────────────────────────────────────────────────  │
│  • Match status: scheduled → live → processing → ready              │
│  • Processing stage: pending → ingested → stitched → ...            │
│  • Error tracking, retry counts                                     │
│  • Artifact paths (MinIO references)                                │
│                                                                      │
│  WHY NOT CLICKHOUSE?                                                │
│  ─────────────────────────────────────────────────────────────────  │
│  • ClickHouse is INSERT-only (no UPDATE/DELETE in typical use)      │
│  • No foreign key constraints                                       │
│  • No ACID transactions                                             │
│  • Metadata needs relationships and updates                         │
│                                                                      │
│  PostgreSQL provides:                                               │
│  + ACID transactions (job state transitions)                        │
│  + Foreign keys (referential integrity)                             │
│  + Indexes for point queries                                        │
│  + Extensions (PostGIS if needed, pg_stat_statements)              │
└─────────────────────────────────────────────────────────────────────┘
```

### PostgreSQL Schema Example / Пример схемы PostgreSQL

```sql
-- Match entity with status tracking
CREATE TYPE match_status AS ENUM (
    'scheduled', 'live', 'processing', 'ready', 'failed'
);

CREATE TYPE processing_stage AS ENUM (
    'pending', 'ingested', 'stitched', 'detected',
    'analyzed', 'encoded', 'complete'
);

CREATE TABLE matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) NOT NULL,
    rig_id UUID REFERENCES camera_rigs(id) NOT NULL,
    calibration_id UUID REFERENCES calibration_versions(id) NOT NULL,

    -- Match info
    home_team VARCHAR(100),
    away_team VARCHAR(100),
    scheduled_at TIMESTAMPTZ NOT NULL,

    -- Status tracking (ACID updates)
    status match_status DEFAULT 'scheduled',
    processing_stage processing_stage DEFAULT 'pending',
    processing_error TEXT,

    -- Artifact paths (MinIO references)
    panorama_path VARCHAR(500),
    virtual_cam_path VARCHAR(500),
    hls_manifest_path VARCHAR(500),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Detection dataset metadata (actual data in ClickHouse)
CREATE TABLE detection_datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id UUID REFERENCES matches(id) NOT NULL,
    model_version VARCHAR(100) NOT NULL,

    -- Statistics (aggregated from ClickHouse)
    total_frames BIGINT,
    total_detections BIGINT,
    ball_detection_rate DECIMAL(4, 3),

    -- Archive path (Parquet backup from ClickHouse)
    archive_detections_path VARCHAR(500),
    archived_at TIMESTAMPTZ,

    UNIQUE(match_id, model_version)
);
```

---

## Decision 4: MinIO/Ceph for Binary Objects
## Решение 4: MinIO/Ceph для бинарных объектов

### Object Storage Strategy / Стратегия объектного хранилища

```
┌─────────────────────────────────────────────────────────────────────┐
│                    OBJECT STORAGE LAYOUT                             │
│                                                                      │
│  MinIO (current) → Ceph (planned for large scale)                   │
│  S3-compatible API ensures transparent migration                    │
│                                                                      │
│  sports-analytics/                                                  │
│  ├── calibrations/{rig_id}/{version}/                              │
│  │   ├── lut_left_x.bin, lut_left_y.bin                            │
│  │   ├── lut_right_x.bin, lut_right_y.bin                          │
│  │   ├── weight_left.bin, weight_right.bin                         │
│  │   └── metadata.json                                              │
│  │                                                                   │
│  ├── models/detector/{version}/                                     │
│  │   ├── detector_edge.engine      # Jetson TensorRT               │
│  │   ├── detector_server.engine    # Server TensorRT               │
│  │   └── metadata.json                                              │
│  │                                                                   │
│  ├── matches/{match_id}/                                            │
│  │   ├── raw/                                                       │
│  │   │   ├── left.mp4              # ~50 GB                        │
│  │   │   └── right.mp4             # ~50 GB                        │
│  │   ├── processed/                                                 │
│  │   │   ├── panorama.mp4          # ~8 GB                         │
│  │   │   └── virtual_camera.mp4    # ~4 GB                         │
│  │   ├── hls/                                                       │
│  │   │   ├── master.m3u8                                            │
│  │   │   └── 1080p/, 720p/, 480p/  # ~2 GB total                   │
│  │   └── analytics/                                                 │
│  │       └── summary.json          # Pre-computed stats            │
│  │                                                                   │
│  └── archive/detections/{match_id}/                                 │
│      ├── detections.parquet        # ~200 MB (from ClickHouse)     │
│      ├── trajectories.parquet                                       │
│      └── export_metadata.json                                       │
│                                                                      │
│  Data lifecycle:                                                    │
│  • Raw video: 7 days hot → 90 days warm → 2 years cold → delete    │
│  • Panorama: 30 days hot → 1 year warm → regenerate if needed      │
│  • HLS: 7 days → delete (regenerable from vcam)                    │
│  • Detection archive: 2 years → delete                              │
└─────────────────────────────────────────────────────────────────────┘
```

### MinIO to Ceph Migration Path / Путь миграции MinIO -> Ceph

```
┌─────────────────────────────────────────────────────────────────────┐
│                  STORAGE MIGRATION STRATEGY                          │
│                                                                      │
│  Phase 1: MinIO (Current)                                           │
│  ─────────────────────────────────────────────────────────────────  │
│  • Development and small-scale production                           │
│  • Single-node or small cluster                                     │
│  • NVMe storage for hot tier                                        │
│                                                                      │
│  Phase 2: MinIO + Ceph (Transition)                                 │
│  ─────────────────────────────────────────────────────────────────  │
│                                                                      │
│  ┌─────────────────┐                                                │
│  │ MinIO (Hot)     │ <-- Recent data, fast access                   │
│  │ NVMe/SSD        │     7-30 days                                  │
│  └────────┬────────┘                                                │
│           │ Lifecycle transition                                    │
│           ▼                                                          │
│  ┌─────────────────┐                                                │
│  │ Ceph (Cold)     │ <-- Older data, erasure coded                  │
│  │ HDD + EC        │     30+ days                                   │
│  │ 10x cost saving │                                                │
│  └─────────────────┘                                                │
│                                                                      │
│  Phase 3: Ceph Only (Large Scale)                                   │
│  ─────────────────────────────────────────────────────────────────  │
│  • Ceph serves all tiers                                            │
│  • NVMe pool for hot, HDD pool for cold                             │
│  • Erasure coding for cost efficiency                               │
│  • Petabyte-scale capacity                                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Summary / Резюме потока данных

```
┌─────────────────────────────────────────────────────────────────────┐
│                    COMPLETE DATA FLOW                                │
│                                                                      │
│  1. INGESTION                                                       │
│     Edge device → raw videos → MinIO                                │
│     Manifest + metadata → PostgreSQL                                │
│                                                                      │
│  2. PROCESSING (Celery workers)                                     │
│     redis-celery: task queue                                        │
│     MinIO: read raw → write panorama, vcam                          │
│     PostgreSQL: update match status                                 │
│                                                                      │
│  3. DETECTION                                                       │
│     Read panorama from MinIO                                        │
│     Run detection model                                             │
│     INSERT detections → ClickHouse (~4.5M rows)                    │
│     Update detection_dataset metadata → PostgreSQL                  │
│                                                                      │
│  4. ANALYTICS                                                       │
│     ClickHouse: materialized views auto-compute                     │
│     Heatmaps, ball timeline, frame stats                            │
│     Pre-rendered results → MinIO (JSON)                             │
│                                                                      │
│  5. DELIVERY                                                        │
│     HLS segments → MinIO → CDN → Viewers                           │
│     redis-cache: API response caching                               │
│                                                                      │
│  6. ARCHIVAL                                                        │
│     Weekly: ClickHouse → Parquet → MinIO                           │
│     90-day TTL: ClickHouse auto-deletes old data                   │
│     2-year: S3 lifecycle deletes archive                            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Interview Questions / Вопросы для интервью

**Q1: Why did Polyvision choose ClickHouse over PostgreSQL for detection data?**

A: Detection data has ~4.5M records per match, which is analytically intensive (aggregations, time-range queries, heatmaps). ClickHouse's columnar storage provides 10-40x compression and sub-second analytical queries. PostgreSQL's row-based storage would struggle with these workloads. Additionally, ClickHouse's materialized views auto-compute aggregations on INSERT. PostgreSQL remains the right choice for metadata (matches, users, jobs) where ACID transactions and relationships are needed.

**Q2: Explain the dual Redis architecture and why it's necessary.**

A: Polyvision uses two Redis instances with different eviction policies: (1) `redis-cache` with `allkeys-lru` - when memory fills, evicts least-recently-used keys. Cache misses just mean slower queries (acceptable). (2) `redis-celery` with `noeviction` - when memory fills, rejects writes with errors. This prevents silent task loss which would cause processing jobs to never complete. A single Redis cannot serve both purposes because losing cached data is acceptable but losing Celery tasks is catastrophic.

**Q3: How does Polyvision handle the detection data lifecycle?**

A: Detection data follows a three-tier lifecycle: (1) Hot tier (ClickHouse, 90 days): Real-time queries, materialized views, sub-second analytics. Data partitioned by `toYYYYMM(created_at)` with TTL auto-deletion. (2) Warm tier (Parquet in MinIO, 2 years): Weekly export from ClickHouse before TTL expires. Compressed Parquet for cost efficiency. Can be restored to ClickHouse if needed. (3) Cold tier (deleted after 2 years): S3 lifecycle policy removes old archives. Raw video (source of truth) has separate, longer retention.

---

## Связано с

- [[Polyvision]]
- [[TimeSeries-DB]]
- [[Redis-Patterns]]
- [[SQL-vs-NoSQL]]

## Ресурсы

- [ADR-021: ClickHouse for Detection Time Series](../../decisions.md#adr-021-clickhouse-for-detection-time-series-data)
- [Polyvision Database Schema](../../architecture/database.md)
- [Polyvision Storage Architecture](../../architecture/storage.md)
- [Redis Eviction Policies](https://redis.io/docs/reference/eviction/)
- [ClickHouse Partitioning Best Practices](https://clickhouse.com/docs/managing-data/core-concepts/partitions)
- [Celery + Redis as Broker](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html)

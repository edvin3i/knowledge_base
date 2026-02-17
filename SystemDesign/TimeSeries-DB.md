---
tags:
  - system-design
  - databases
  - timeseries
  - clickhouse
created: 2026-02-17
---

# Time Series Databases: ClickHouse, TimescaleDB, InfluxDB
# Базы данных временных рядов: ClickHouse, TimescaleDB, InfluxDB

> **Reading time:** ~18 min | **Время чтения:** ~18 мин

## Что это

Сравнение трёх ведущих баз данных временных рядов: [[ClickHouse]] (колоночная OLAP), TimescaleDB (расширение PostgreSQL), InfluxDB (специализированная TSDB). Архитектура, схемы, запросы, производительность, фреймворк выбора.

Time series data is one of the fastest-growing data categories. From IoT sensors to financial markets to observability metrics, systems generate billions of timestamped records daily. This document compares three leading time series databases and their architectural approaches.

Данные временных рядов — одна из самых быстрорастущих категорий данных. От IoT-сенсоров до финансовых рынков и метрик наблюдаемости — системы генерируют миллиарды записей с временными метками ежедневно. Этот документ сравнивает три ведущие базы данных временных рядов.

---

## What is Time Series Data? / Что такое временные ряды?

```
┌─────────────────────────────────────────────────────────────────────┐
│                     TIME SERIES DATA CHARACTERISTICS                 │
│                                                                      │
│  1. TIMESTAMP AS PRIMARY KEY                                        │
│     Every record has a timestamp                                    │
│     Каждая запись имеет временную метку                             │
│                                                                      │
│  2. APPEND-MOSTLY                                                   │
│     New data is inserted, rarely updated or deleted                 │
│     Новые данные вставляются, редко обновляются или удаляются       │
│                                                                      │
│  3. TIME-ORDERED QUERIES                                            │
│     Most queries filter by time range                               │
│     Большинство запросов фильтруют по временному диапазону          │
│                                                                      │
│  4. AGGREGATION HEAVY                                               │
│     Common: avg, sum, min, max over time windows                    │
│     Обычные: avg, sum, min, max по временным окнам                  │
│                                                                      │
│  Example data pattern:                                               │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ timestamp            │ device_id │ temperature │ humidity   │    │
│  │ 2026-01-12 10:00:00  │ sensor-1  │ 23.5        │ 65.2       │    │
│  │ 2026-01-12 10:00:01  │ sensor-1  │ 23.6        │ 65.1       │    │
│  │ 2026-01-12 10:00:02  │ sensor-1  │ 23.5        │ 65.3       │    │
│  │ ...                  │ ...       │ ...         │ ...        │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### Common Use Cases / Распространённые случаи использования

| Category | Examples | Data Volume |
|----------|----------|-------------|
| **Observability** | Metrics, logs, traces | Billions/day |
| **IoT** | Sensors, devices, vehicles | Millions/device/day |
| **Finance** | Stock prices, trades, ticks | Millions/second (peak) |
| **Gaming/Sports** | Player positions, events | ~4.5M/match ([[Polyvision]]) |
| **Infrastructure** | Server metrics, network stats | Thousands/host/minute |

---

## ClickHouse / ClickHouse

### Architecture Overview / Обзор архитектуры

ClickHouse is a columnar OLAP database designed for real-time analytical queries on large datasets.

ClickHouse — это колоночная OLAP база данных для аналитических запросов в реальном времени на больших наборах данных.

```
┌─────────────────────────────────────────────────────────────────────┐
│                      CLICKHOUSE ARCHITECTURE                         │
│                                                                      │
│  Query                                                               │
│    │                                                                 │
│    ▼                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Query Parser & Optimizer                   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Distributed Query Engine                   │    │
│  │           (parallel execution across shards)                  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│         │                    │                    │                  │
│         ▼                    ▼                    ▼                  │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐          │
│  │   Shard 1   │      │   Shard 2   │      │   Shard 3   │          │
│  │             │      │             │      │             │          │
│  │  ┌───────┐  │      │  ┌───────┐  │      │  ┌───────┐  │          │
│  │  │Part 1 │  │      │  │Part 1 │  │      │  │Part 1 │  │          │
│  │  ├───────┤  │      │  ├───────┤  │      │  ├───────┤  │          │
│  │  │Part 2 │  │      │  │Part 2 │  │      │  │Part 2 │  │          │
│  │  ├───────┤  │      │  ├───────┤  │      │  ├───────┤  │          │
│  │  │Part N │  │      │  │Part N │  │      │  │Part N │  │          │
│  │  └───────┘  │      │  └───────┘  │      │  └───────┘  │          │
│  └─────────────┘      └─────────────┘      └─────────────┘          │
│                                                                      │
│  COLUMNAR STORAGE (per part):                                       │
│  ┌─────┬─────┬──────────┬──────────┬───────────┬──────────┐         │
│  │ ts  │ id  │ temp.bin │ temp.mrk │ hum.bin   │ hum.mrk  │         │
│  │.bin │.bin │          │          │           │          │         │
│  └─────┴─────┴──────────┴──────────┴───────────┴──────────┘         │
│                                                                      │
│  Key features:                                                       │
│  • Columnar compression (10-40x)                                    │
│  • Vectorized query execution (SIMD)                                │
│  • MergeTree engine family                                          │
│  • Materialized views for pre-aggregation                           │
└─────────────────────────────────────────────────────────────────────┘
```

### ClickHouse Schema Example / Пример схемы ClickHouse

```sql
-- Detection data for sports analytics (Polyvision example)
CREATE TABLE detections (
    organization_id UUID,
    match_id UUID,
    frame_idx UInt32,
    pts Int64,
    wallclock_ns Int64,
    created_at DateTime DEFAULT now(),

    class_id UInt8,         -- 0=ball, 1=player, etc.
    confidence Float32,
    x Float32, y Float32,
    width Float32, height Float32,

    tile_id UInt8,
    track_id Nullable(UInt32),
    model_version LowCardinality(String)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(created_at)       -- Monthly partitions
ORDER BY (organization_id, match_id, frame_idx, class_id)
TTL created_at + INTERVAL 90 DAY DELETE -- Auto-cleanup
SETTINGS ttl_only_drop_parts = 1;

-- Materialized view for automatic aggregation
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
```

### ClickHouse Strengths / Сильные стороны ClickHouse

| Feature | Benefit |
|---------|---------|
| **Columnar storage** | 10-40x compression, fast scans |
| **Vectorized execution** | SIMD operations, billions rows/sec |
| **SQL interface** | Familiar syntax, easy adoption |
| **Materialized views** | Auto-computed aggregations |
| **Partitioning + TTL** | Efficient data lifecycle |
| **No external dependencies** | No ZooKeeper (with ClickHouse Keeper) |

### ClickHouse Query Examples / Примеры запросов ClickHouse

```sql
-- Get ball positions for a match (sub-second on millions of rows)
SELECT frame_idx, x, y, confidence
FROM detections
WHERE organization_id = '{org_id}'
  AND match_id = '{match_id}'
  AND class_id = 0  -- ball
ORDER BY frame_idx;

-- Heatmap aggregation (uses materialized view)
SELECT grid_x, grid_y, sum(presence_count) as count
FROM heatmap_grid_mv
WHERE organization_id = '{org_id}'
  AND match_id = '{match_id}'
  AND class_id = 1  -- players
GROUP BY grid_x, grid_y;

-- Cross-match analytics
SELECT
    match_id,
    count() as detections,
    avg(confidence) as avg_confidence
FROM detections
WHERE organization_id = '{org_id}'
  AND created_at > now() - INTERVAL 30 DAY
GROUP BY match_id
ORDER BY detections DESC
LIMIT 10;
```

---

## TimescaleDB / TimescaleDB

### Architecture Overview / Обзор архитектуры

TimescaleDB is a PostgreSQL extension that adds time series capabilities while maintaining full SQL compatibility.

TimescaleDB — это расширение PostgreSQL, добавляющее возможности временных рядов при сохранении полной совместимости с SQL.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TIMESCALEDB ARCHITECTURE                          │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    PostgreSQL Core                           │    │
│  │   • Query planner                                            │    │
│  │   • ACID transactions                                        │    │
│  │   • Full SQL support                                         │    │
│  │   • Extensions (PostGIS, etc.)                               │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                 TimescaleDB Extension                         │    │
│  │                                                               │    │
│  │   HYPERTABLES (automatic partitioning)                       │    │
│  │   ┌───────────────────────────────────────────────────────┐  │    │
│  │   │  Hypertable: sensor_data                               │  │    │
│  │   │                                                         │  │    │
│  │   │  ┌─────────┬─────────┬─────────┬─────────┬─────────┐  │  │    │
│  │   │  │ Chunk 1 │ Chunk 2 │ Chunk 3 │ Chunk 4 │ Chunk N │  │  │    │
│  │   │  │ Jan 1-7 │ Jan 8-14│Jan 15-21│Jan 22-28│  ...    │  │  │    │
│  │   │  └─────────┴─────────┴─────────┴─────────┴─────────┘  │  │    │
│  │   └───────────────────────────────────────────────────────┘  │    │
│  │                                                               │    │
│  │   CONTINUOUS AGGREGATES                                      │    │
│  │   • Automatic materialized views                             │    │
│  │   • Incremental refresh                                      │    │
│  │   • Real-time + materialized data                            │    │
│  │                                                               │    │
│  │   COMPRESSION                                                │    │
│  │   • Column-based compression                                 │    │
│  │   • Per-chunk compression policies                           │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

### TimescaleDB Schema Example / Пример схемы TimescaleDB

```sql
-- Create hypertable for sensor data
CREATE TABLE sensor_data (
    time        TIMESTAMPTZ NOT NULL,
    device_id   TEXT NOT NULL,
    temperature DOUBLE PRECISION,
    humidity    DOUBLE PRECISION
);

-- Convert to hypertable (automatic time-based partitioning)
SELECT create_hypertable('sensor_data', 'time',
    chunk_time_interval => INTERVAL '1 day');

-- Add compression policy
ALTER TABLE sensor_data SET (
    timescaledb.compress,
    timescaledb.compress_orderby = 'time DESC',
    timescaledb.compress_segmentby = 'device_id'
);

-- Automatically compress chunks older than 7 days
SELECT add_compression_policy('sensor_data', INTERVAL '7 days');

-- Create continuous aggregate for hourly stats
CREATE MATERIALIZED VIEW sensor_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    device_id,
    avg(temperature) AS avg_temp,
    max(temperature) AS max_temp,
    min(temperature) AS min_temp
FROM sensor_data
GROUP BY bucket, device_id;

-- Add refresh policy
SELECT add_continuous_aggregate_policy('sensor_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');
```

### TimescaleDB Strengths / Сильные стороны TimescaleDB

| Feature | Benefit |
|---------|---------|
| **Full PostgreSQL** | JOINs, ACID, extensions |
| **Automatic partitioning** | Hypertables handle chunking |
| **Continuous aggregates** | Incremental materialized views |
| **Compression** | 90%+ compression on older data |
| **Data retention** | Built-in retention policies |
| **Existing tools** | pgAdmin, psycopg2, ORMs work |

---

## InfluxDB / InfluxDB

### Architecture Overview / Обзор архитектуры

InfluxDB is purpose-built for metrics and events with a specialized data model and query language.

InfluxDB специально создана для метрик и событий со специализированной моделью данных и языком запросов.

```
┌─────────────────────────────────────────────────────────────────────┐
│                      INFLUXDB ARCHITECTURE                           │
│                                                                      │
│  DATA MODEL                                                         │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  measurement: cpu                                            │    │
│  │  ─────────────────────────────────────────────────          │    │
│  │  tags (indexed):    host=server1, region=us-west            │    │
│  │  fields (values):   usage=45.2, idle=54.8                   │    │
│  │  timestamp:         2026-01-12T10:00:00Z                    │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  STORAGE ENGINE (TSI - Time Series Index)                           │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  ┌───────────────────────────────────────────────────────┐  │    │
│  │  │               Write-Ahead Log (WAL)                    │  │    │
│  │  └───────────────────────────────────────────────────────┘  │    │
│  │                           │                                  │    │
│  │                           ▼                                  │    │
│  │  ┌───────────────────────────────────────────────────────┐  │    │
│  │  │                      Cache                             │  │    │
│  │  └───────────────────────────────────────────────────────┘  │    │
│  │                           │                                  │    │
│  │                           ▼ (compaction)                    │    │
│  │  ┌─────────┬─────────┬─────────┬─────────┬─────────┐       │    │
│  │  │  TSM 1  │  TSM 2  │  TSM 3  │  TSM 4  │  TSM N  │       │    │
│  │  │ (block) │ (block) │ (block) │ (block) │ (block) │       │    │
│  │  └─────────┴─────────┴─────────┴─────────┴─────────┘       │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  INFLUXDB 3.0 (New Architecture)                                    │
│  • Apache Arrow columnar format                                     │
│  • Object storage native (S3)                                       │
│  • SQL support alongside Flux                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### InfluxDB Query Examples / Примеры запросов InfluxDB

```flux
// Flux query language (InfluxDB 2.x)

// Get CPU usage for last hour
from(bucket: "metrics")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "cpu")
  |> filter(fn: (r) => r._field == "usage")
  |> filter(fn: (r) => r.host == "server1")

// Aggregate by 5-minute windows
from(bucket: "metrics")
  |> range(start: -24h)
  |> filter(fn: (r) => r._measurement == "cpu")
  |> aggregateWindow(every: 5m, fn: mean)
  |> yield(name: "cpu_5m_avg")

// InfluxDB 3.0 SQL support
SELECT
    time_bucket('5 minutes', time) as bucket,
    host,
    avg(usage) as avg_usage
FROM cpu
WHERE time > now() - INTERVAL '1 day'
GROUP BY bucket, host
ORDER BY bucket;
```

### InfluxDB Strengths / Сильные стороны InfluxDB

| Feature | Benefit |
|---------|---------|
| **Purpose-built** | Optimized for metrics/events |
| **Tag-based indexing** | Fast dimension filtering |
| **Flux language** | Powerful transformations |
| **Built-in dashboards** | Chronograf UI |
| **Telegraf ecosystem** | 200+ input plugins |
| **Cloud offering** | Fully managed option |

---

## Comparison Table / Сравнительная таблица

| Aspect | ClickHouse | TimescaleDB | InfluxDB |
|--------|------------|-------------|----------|
| **Type** | Columnar OLAP | PostgreSQL extension | Purpose-built TSDB |
| **Query language** | SQL | SQL | Flux + SQL (v3) |
| **ACID** | Partial (insert only) | Full | Partial |
| **JOINs** | Yes | Yes (full SQL) | Limited |
| **Compression** | 10-40x | 90%+ (older data) | 10x+ |
| **Ingestion speed** | Millions/sec | Hundreds of K/sec | Hundreds of K/sec |
| **Query speed** | Fastest for OLAP | Good | Good for metrics |
| **Learning curve** | Low (SQL) | Low (PostgreSQL) | Medium (Flux) |
| **Best for** | Analytics, logs | Mixed workloads | Metrics, IoT |
| **Maturity** | 2016, mature | 2017, mature | 2013, mature |

### Performance Characteristics / Характеристики производительности

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PERFORMANCE COMPARISON                            │
│                                                                      │
│  INSERT THROUGHPUT (rows/second on commodity hardware)              │
│  ─────────────────────────────────────────────────────              │
│  ClickHouse:  ████████████████████████████████████ ~1M+/sec         │
│  TimescaleDB: ████████████████████ ~200-500K/sec                    │
│  InfluxDB:    ████████████████████ ~200-500K/sec                    │
│                                                                      │
│  ANALYTICAL QUERY (scan 100M rows, GROUP BY)                        │
│  ────────────────────────────────────────────                       │
│  ClickHouse:  ████ <1 sec                                           │
│  TimescaleDB: ████████████ 2-5 sec                                  │
│  InfluxDB:    ████████████████ 3-8 sec                              │
│                                                                      │
│  POINT QUERY (single time series, 1 hour window)                    │
│  ───────────────────────────────────────────────                    │
│  ClickHouse:  ████ <100ms                                           │
│  TimescaleDB: ████ <100ms                                           │
│  InfluxDB:    ████ <100ms                                           │
│                                                                      │
│  COMPRESSION RATIO                                                   │
│  ──────────────────                                                  │
│  ClickHouse:  ████████████████████████████████ 10-40x               │
│  TimescaleDB: ████████████████████████████ 8-15x (compressed)       │
│  InfluxDB:    ████████████████████████ 7-12x                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Choosing the Right Database / Выбор правильной базы данных

### Decision Framework / Фреймворк принятия решений

```
┌─────────────────────────────────────────────────────────────────────┐
│                      DECISION FRAMEWORK                              │
│                                                                      │
│  Q1: Do you need full SQL with JOINs and ACID?                      │
│  ├── YES → TimescaleDB (PostgreSQL compatibility)                   │
│  └── NO → Continue                                                   │
│                                                                      │
│  Q2: Is your primary use case metrics collection?                   │
│  ├── YES → InfluxDB (purpose-built, Telegraf ecosystem)            │
│  └── NO → Continue                                                   │
│                                                                      │
│  Q3: Do you need sub-second analytics on billions of rows?          │
│  ├── YES → ClickHouse (fastest OLAP queries)                        │
│  └── NO → Consider workload mix                                      │
│                                                                      │
│  Q4: Mixed OLTP + analytics on same data?                           │
│  ├── YES → TimescaleDB (single database, both workloads)           │
│  └── NO → Polyglot (OLTP DB + ClickHouse)                           │
│                                                                      │
│  Q5: Team PostgreSQL expertise?                                     │
│  ├── HIGH → TimescaleDB (familiar tooling)                          │
│  └── LOW → ClickHouse (simple SQL, good docs)                       │
└─────────────────────────────────────────────────────────────────────┘
```

### Use Case Recommendations / Рекомендации по случаям использования

| Use Case | Recommended | Why |
|----------|-------------|-----|
| **Sports analytics** ([[Polyvision]]) | ClickHouse | ~4.5M detections/match, analytical queries |
| **Server metrics** | InfluxDB | Telegraf integration, purpose-built |
| **Financial data** | TimescaleDB | ACID needed, complex queries |
| **Log analysis** | ClickHouse | High volume, full-text search |
| **IoT sensors** | InfluxDB/ClickHouse | Depends on query patterns |
| **Mixed workload** | TimescaleDB | OLTP + analytics in one DB |

---

## Hybrid Architectures / Гибридные архитектуры

Modern systems often combine databases for different workloads:

Современные системы часто комбинируют базы данных для разных нагрузок:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     HYBRID ARCHITECTURE EXAMPLE                      │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                     APPLICATION LAYER                          │  │
│  └───────────────────────────────────────────────────────────────┘  │
│         │                    │                    │                  │
│         ▼                    ▼                    ▼                  │
│  ┌───────────────┐   ┌───────────────┐   ┌───────────────┐          │
│  │  PostgreSQL   │   │  ClickHouse   │   │    Redis      │          │
│  │               │   │               │   │               │          │
│  │ • Metadata    │   │ • Time series │   │ • Cache       │          │
│  │ • Users       │   │ • Analytics   │   │ • Sessions    │          │
│  │ • Config      │   │ • Aggregates  │   │ • Hot data    │          │
│  │ • Jobs        │   │               │   │               │          │
│  └───────────────┘   └───────────────┘   └───────────────┘          │
│         │                    │                    │                  │
│         │                    │                    │                  │
│  ┌──────┴────────────────────┴────────────────────┴──────┐          │
│  │                     MinIO (S3)                         │          │
│  │              Long-term Parquet archives                │          │
│  └───────────────────────────────────────────────────────┘          │
│                                                                      │
│  Data flow:                                                         │
│  1. Worker INSERTs detections → ClickHouse                          │
│  2. ClickHouse MVs auto-compute aggregates                          │
│  3. PostgreSQL stores metadata (match info, dataset version)        │
│  4. Weekly backup: ClickHouse → Parquet → MinIO                     │
│  5. Redis caches frequent queries                                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Interview Questions / Вопросы для интервью

**Q1: Why would you choose ClickHouse over TimescaleDB for analytics?**

A: ClickHouse is a columnar OLAP database designed specifically for analytical queries. It excels at: (1) Scanning billions of rows in seconds due to columnar storage and vectorized execution, (2) Aggressive compression (10-40x), (3) Parallel query execution across shards. TimescaleDB, being a PostgreSQL extension, maintains row-based storage which is slower for full-table scans but better for point queries and mixed workloads requiring ACID transactions.

**Q2: How do materialized views differ between ClickHouse and TimescaleDB?**

A: In ClickHouse, materialized views are updated synchronously on INSERT - data is transformed and written to the target table immediately. SummingMergeTree and AggregatingMergeTree engines allow incremental aggregation. In TimescaleDB, continuous aggregates are updated asynchronously via background refresh jobs, with configurable refresh intervals. TimescaleDB also supports real-time aggregates that combine materialized data with fresh data automatically.

**Q3: What are the tradeoffs of using a specialized TSDB vs a general-purpose database?**

A: Specialized TSDBs (InfluxDB, ClickHouse) offer: (1) Optimized storage for time-ordered data, (2) Built-in time-based functions (downsampling, windowing), (3) Better compression for numeric sequences, (4) Native retention policies. Tradeoffs: (1) Limited JOIN capabilities, (2) Learning new query languages (Flux), (3) Separate system to operate, (4) Data movement if you need to JOIN with relational data. General-purpose databases like PostgreSQL with TimescaleDB offer familiar SQL and easier integration but may not match specialized databases' performance.

## Связано с

- [[SQL-vs-NoSQL]]
- [[PV-Storage]]

## Ресурсы

- [ClickHouse Documentation](https://clickhouse.com/docs/)
- [TimescaleDB Documentation](https://docs.timescale.com/)
- [InfluxDB Documentation](https://docs.influxdata.com/)
- [ClickHouse vs TimescaleDB Benchmark](https://benchmark.clickhouse.com/)
- [Time Series Database Comparison (DB-Engines)](https://db-engines.com/en/ranking/time+series+dbms)
- [Designing Data-Intensive Applications - Martin Kleppmann](https://dataintensive.net/)

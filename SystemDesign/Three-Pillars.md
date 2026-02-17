---
tags:
  - system-design
  - observability
  - metrics
  - logs
  - traces
created: 2026-02-17
---

# Три столпа наблюдаемости / The Three Pillars of Observability

## Что это

Наблюдаемость (Observability) — способность понимать внутреннее состояние системы по внешним выходам. Три столпа: метрики (числовые измерения), логи (записи событий), трейсы (путь запроса). Ключевые методы: RED (Rate/Errors/Duration) для сервисов, USE (Utilization/Saturation/Errors) для ресурсов. Корреляция между столпами через trace_id.

---

## Introduction / Введение

Observability is the ability to understand the internal state of a system by examining its external outputs. In distributed systems, this becomes critical as traditional debugging approaches fail when requests traverse multiple services.

Наблюдаемость — это способность понимать внутреннее состояние системы путём анализа её внешних выходов. В распределённых системах это становится критически важным, так как традиционные методы отладки не работают, когда запросы проходят через множество сервисов.

---

## What is Observability? / Что такое наблюдаемость?

### Definition / Определение

Observability originates from control theory: a system is observable if you can determine its internal state from its outputs. In software, this translates to instrumenting systems to emit telemetry data.

```
+-------------------+     +-------------------+     +-------------------+
|                   |     |                   |     |                   |
|   APPLICATION     |---->|    TELEMETRY      |---->|    ANALYSIS       |
|                   |     |   (M, L, T)       |     |   PLATFORM        |
+-------------------+     +-------------------+     +-------------------+
        |                         |                         |
        v                         v                         v
   Instrumentation          Collection             Visualization
   (SDK, Agent)            (Collector)            (Dashboards)
```

### Monitoring vs Observability / Мониторинг vs Наблюдаемость

| Aspect | Monitoring | Observability |
|--------|------------|---------------|
| **Approach** | Predefined dashboards | Exploratory analysis |
| **Questions** | Known unknowns | Unknown unknowns |
| **Data** | Aggregated metrics | High-cardinality data |
| **Use case** | Alert on thresholds | Debug novel issues |
| **Philosophy** | "Is it broken?" | "Why is it broken?" |

---

## Pillar 1: Metrics / Столп 1: Метрики

### What Are Metrics? / Что такое метрики?

Metrics are numerical measurements collected at regular intervals. They are highly efficient for storage and querying, making them ideal for dashboards and alerting.

```
Metric Structure:
+------------------+------------------+------------------+
|     METRIC       |     LABELS       |     VALUE        |
+------------------+------------------+------------------+
| http_requests    | method="GET"     |     1523         |
| _total           | status="200"     |                  |
|                  | endpoint="/api"  |                  |
+------------------+------------------+------------------+
```

### Metric Types / Типы метрик

| Type | Description | Example |
|------|-------------|---------|
| **Counter** | Monotonically increasing value | Total requests, errors |
| **Gauge** | Value that can go up or down | Current memory, temperature |
| **Histogram** | Distribution of values in buckets | Request latency |
| **Summary** | Pre-calculated quantiles | P50, P95, P99 latencies |

### RED and USE Methods / Методы RED и USE

**RED Method** (for request-driven services):
- **R**ate -- Requests per second
- **E**rrors -- Failed requests per second
- **D**uration -- Latency distribution

**USE Method** (for resources):
- **U**tilization -- Percentage of resource used
- **S**aturation -- Queue depth, work waiting
- **E**rrors -- Error events count

```python
# Example: Prometheus metrics in Python
from prometheus_client import Counter, Histogram, Gauge

# RED metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)

# USE metrics
cpu_utilization = Gauge(
    'cpu_utilization_percent',
    'CPU utilization percentage'
)
```

---

## Pillar 2: Logs / Столп 2: Логи

### What Are Logs? / Что такое логи?

Logs are timestamped, immutable records of discrete events. They provide context and detail that metrics cannot capture.

```
Log Entry Structure:
+------------+----------+------------------------------------------+
| TIMESTAMP  | LEVEL    | MESSAGE + CONTEXT                        |
+------------+----------+------------------------------------------+
| 2026-01-12 | ERROR    | {"msg": "Failed to process video",       |
| 14:30:00Z  |          |  "match_id": "abc123",                   |
|            |          |  "error": "GPU memory exceeded",         |
|            |          |  "trace_id": "4bf92f3577b3..."}          |
+------------+----------+------------------------------------------+
```

### Log Levels / Уровни логирования

| Level | Purpose | Example |
|-------|---------|---------|
| **TRACE** | Fine-grained debugging | Function entry/exit |
| **DEBUG** | Development debugging | Variable values |
| **INFO** | Normal operations | Request completed |
| **WARN** | Potential issues | Retry attempted |
| **ERROR** | Failed operations | Request failed |
| **FATAL** | System crash | Cannot connect to DB |

### Structured Logging / Структурированное логирование

```python
import structlog

logger = structlog.get_logger()

# Structured log with context
logger.info(
    "video_processing_completed",
    match_id="match_abc123",
    duration_seconds=45.2,
    frame_count=162000,
    trace_id=span.context.trace_id
)

# Output (JSON):
# {
#     "timestamp": "2026-01-12T14:30:00Z",
#     "level": "info",
#     "event": "video_processing_completed",
#     "match_id": "match_abc123",
#     "duration_seconds": 45.2,
#     "frame_count": 162000,
#     "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736"
# }
```

---

## Pillar 3: Traces / Столп 3: Трейсы

### What Are Traces? / Что такое трейсы?

Traces represent the end-to-end journey of a request through a distributed system. A trace consists of multiple spans, each representing a unit of work.

```
Trace Visualization:

Service A  |=====[Span 1: API Request]===================|
           |                                              |
Service B  |     |===[Span 2: Auth]===|                  |
           |                           |                  |
Service C  |                           |==[Span 3: DB]==| |
           |                                              |
           +----------------------------------------------+
           0ms                                         100ms

Span Structure:
+------------------+----------------------------------------+
| Field            | Example                                |
+------------------+----------------------------------------+
| trace_id         | 4bf92f3577b34da6a3ce929d0e0e4736      |
| span_id          | 00f067aa0ba902b7                       |
| parent_span_id   | 7b7b7b7b7b7b7b7b                       |
| operation_name   | POST /api/matches/process              |
| start_time       | 2026-01-12T14:30:00.000Z              |
| duration_ms      | 245                                    |
| status           | OK                                     |
| attributes       | {"match_id": "abc123", "stage": "..."}|
+------------------+----------------------------------------+
```

### Context Propagation / Распространение контекста

```
Request Flow with Context:

Client --> Service A --> Service B --> Service C --> Database
           |             |             |
           v             v             v
      [trace_id,    [trace_id,    [trace_id,
       span_id_1]    span_id_2]    span_id_3]
           |             |             |
           +-------------+-------------+
                         |
              W3C TraceContext Headers:
              traceparent: 00-{trace_id}-{span_id}-01
              tracestate: vendor=value
```

### Trace Sampling Strategies / Стратегии сэмплирования

| Strategy | Description | Use Case |
|----------|-------------|----------|
| **Head-based** | Decide at request start | High-volume, low-latency |
| **Tail-based** | Decide after trace complete | Capture errors, slow requests |
| **Probabilistic** | Random percentage | General purpose |
| **Rate limiting** | Fixed traces/second | Cost control |

---

## Relationships Between Pillars / Связи между столпами

### Correlation / Корреляция

The power of observability comes from correlating data across all three pillars:

```
                    +------------------+
                    |     METRICS      |
                    |   (Aggregated)   |
                    +--------+---------+
                             |
              Alert: Error rate spike
                             |
                             v
                    +------------------+
                    |      LOGS        |
                    |   (Detailed)     |
                    +--------+---------+
                             |
              Filter: trace_id from errors
                             |
                             v
                    +------------------+
                    |     TRACES       |
                    |   (Distributed)  |
                    +------------------+
                             |
              See full request path
```

### Example Workflow / Пример рабочего процесса

```
1. ALERT (Metrics):
   http_error_rate > 5% for 5 minutes

2. INVESTIGATE (Logs):
   Query: level="error" AND service="video-processor"
   Result: "GPU memory exceeded" with trace_id

3. TRACE (Traces):
   Open trace_id in Jaeger
   See: Stitch -> Detect -> [FAILED at tile batch 15]
   Root cause: Tile batch too large for GPU

4. FIX:
   Reduce batch size, deploy, verify metrics normalize
```

---

## Modern Observability Stack / Современный стек наблюдаемости

```
+------------------------------------------------------------------+
|                        OBSERVABILITY STACK                        |
+------------------------------------------------------------------+
|                                                                   |
|  COLLECTION                   STORAGE              VISUALIZATION  |
|  +---------------+           +-----------+        +------------+  |
|  | OpenTelemetry |---------->| Prometheus|------->|  Grafana   |  |
|  | Collector     |     |     | (Metrics) |        |            |  |
|  +---------------+     |     +-----------+        |  - Metrics |  |
|                        |                          |  - Logs    |  |
|  +---------------+     |     +-----------+        |  - Traces  |  |
|  | Fluent Bit    |-----|---->| Loki      |------->|            |  |
|  | / Promtail    |     |     | (Logs)    |        +------------+  |
|  +---------------+     |     +-----------+                        |
|                        |                                          |
|                        |     +-----------+        +------------+  |
|                        +---->| Jaeger/   |------->| Jaeger UI  |  |
|                              | Tempo     |        +------------+  |
|                              | (Traces)  |                        |
|                              +-----------+                        |
+------------------------------------------------------------------+
```

---

## Best Practices / Лучшие практики

### 1. Instrument Everything / Инструментируйте всё

```python
# Good: Comprehensive instrumentation
@trace_span("process_video")
def process_video(match_id: str):
    metrics.video_processing_started.inc()

    with metrics.video_processing_duration.time():
        logger.info("Starting processing", match_id=match_id)
        result = do_processing()

    if result.success:
        metrics.video_processing_success.inc()
    else:
        metrics.video_processing_errors.inc()
        logger.error("Processing failed", match_id=match_id, error=result.error)
```

### 2. Use Consistent Labels / Используйте согласованные метки

| Bad | Good |
|-----|------|
| `svc`, `service`, `app` | `service_name` everywhere |
| `err`, `error`, `fail` | `error_type` everywhere |
| Custom trace IDs | W3C TraceContext |

### 3. Set Cardinality Limits / Ограничивайте кардинальность

```python
# BAD: Unbounded cardinality
requests.labels(user_id=user.id)  # Millions of users!

# GOOD: Bounded cardinality
requests.labels(
    endpoint="/api/matches",
    method="POST",
    status_code="2xx"  # Grouped status codes
)
```

### 4. Define SLIs and SLOs / Определите SLI и SLO

```yaml
# Service Level Indicators (SLIs)
slis:
  - name: availability
    metric: sum(rate(http_requests_total{status=~"2.."}[5m])) / sum(rate(http_requests_total[5m]))

  - name: latency_p99
    metric: histogram_quantile(0.99, rate(http_request_duration_bucket[5m]))

# Service Level Objectives (SLOs)
slos:
  - name: availability_slo
    target: 99.9%
    window: 30d

  - name: latency_slo
    target: 500ms
    percentile: 99
    window: 30d
```

---

## Связано с

- [[Prometheus-Grafana]]
- [[Distributed-Tracing]]
- [[Log-Aggregation]]
- [[PV-Monitoring]]

## Ресурсы

1. "Observability Engineering" by Charity Majors, Liz Fong-Jones, George Miranda (O'Reilly, 2022)
2. Google SRE Book: https://sre.google/sre-book/monitoring-distributed-systems/
3. OpenTelemetry Documentation: https://opentelemetry.io/docs/
4. Prometheus Best Practices: https://prometheus.io/docs/practices/naming/
5. Distributed Tracing in Practice by Austin Parker et al. (O'Reilly, 2020)
6. The RED Method by Tom Wilkie: https://grafana.com/blog/2018/08/02/the-red-method-how-to-instrument-your-services/
7. The USE Method by Brendan Gregg: https://www.brendangregg.com/usemethod.html

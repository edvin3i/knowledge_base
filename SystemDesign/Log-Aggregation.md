---
tags:
  - system-design
  - observability
  - elk
  - loki
created: 2026-02-17
---

# Агрегация логов / Log Aggregation: ELK vs Loki

## Что это

Агрегация логов -- централизация логов из распределённых систем. ELK (Elasticsearch, Logstash, Kibana) -- полнотекстовое индексирование всех полей, мощный поиск, высокое потребление ресурсов. Grafana Loki -- индексирует только метки (labels), хранит сжатые логи в объектном хранилище, LogQL для запросов, низкая стоимость. Structured logging (structlog, JSON) обязателен.

---

## Introduction / Введение

Log aggregation centralizes logs from distributed systems into a single, queryable platform. Two dominant approaches exist: the feature-rich ELK stack (Elasticsearch, Logstash, Kibana) and the lightweight Grafana Loki.

Агрегация логов централизует логи из распределённых систем в единую платформу для запросов. Существуют два доминирующих подхода: многофункциональный ELK стек и легковесный Grafana Loki.

---

## Log Aggregation Fundamentals / Основы агрегации логов

### Pipeline Components / Компоненты пайплайна

```
+------------------------------------------------------------------+
|                    LOG AGGREGATION PIPELINE                       |
+------------------------------------------------------------------+
|                                                                   |
|  COLLECTION          TRANSPORT         STORAGE         QUERY      |
|  +----------+       +---------+       +--------+      +-------+   |
|  |Filebeat  |       |         |       |        |      |       |   |
|  |Promtail  |------>| Kafka/  |------>| Index  |----->| UI    |   |
|  |FluentBit |       | Direct  |       | Store  |      |       |   |
|  |Vector    |       |         |       |        |      |       |   |
|  +----------+       +---------+       +--------+      +-------+   |
|       |                  |                 |               |      |
|       v                  v                 v               v      |
|  Parse, filter      Buffer,           Full-text       Dashboards  |
|  add metadata       transform          index          Alerts      |
|                                                                   |
+------------------------------------------------------------------+
```

### Log Entry Lifecycle / Жизненный цикл лог-записи

```
Application Log:
{"level":"error","msg":"Failed to process","match_id":"abc123","trace_id":"4bf92f..."}
                |
                v
+---------------------------+
| COLLECTION (Agent)        |
| - Read from file/stdout   |
| - Parse JSON              |
| - Add labels (host, app)  |
+---------------------------+
                |
                v
+---------------------------+
| TRANSPORT                 |
| - Batch entries           |
| - Compress                |
| - Send to backend         |
+---------------------------+
                |
                v
+---------------------------+
| INGESTION                 |
| - Validate schema         |
| - Index (ELK) or          |
|   Label-only (Loki)       |
+---------------------------+
                |
                v
+---------------------------+
| STORAGE                   |
| - Compress                |
| - Retention policies      |
| - Tiered storage          |
+---------------------------+
                |
                v
+---------------------------+
| QUERY                     |
| - Full-text search        |
| - Field filtering         |
| - Aggregations            |
+---------------------------+
```

---

## ELK Stack Overview / Обзор ELK стека

### Architecture / Архитектура

```
+------------------------------------------------------------------+
|                         ELK STACK                                 |
+------------------------------------------------------------------+
|                                                                   |
|  Log Sources           Ingestion            Search & Viz          |
|  +----------+         +---------+          +------------+         |
|  |App Logs  |         |Logstash |          |            |         |
|  +----+-----+         |  or     |          | Kibana     |         |
|       |               |Ingest   |          |  - Discover|         |
|       v               |Node     |          |  - Lens    |         |
|  +----------+         +----+----+          |  - Alerts  |         |
|  |Filebeat  |              |               +------+-----+         |
|  |  or      |--------------+                      |               |
|  |Logstash  |              |                      |               |
|  +----------+              v                      |               |
|                     +-------------+               |               |
|  +----------+       |             |               |               |
|  |Metricbeat|------>|Elasticsearch|<--------------+               |
|  +----------+       |  Cluster    |                               |
|                     |             |                               |
|  +----------+       | +---------+ |                               |
|  |APM Agent |------>| |Data Node| |                               |
|  +----------+       | +---------+ |                               |
|                     | |Data Node| |                               |
|                     | +---------+ |                               |
|                     | |Master   | |                               |
|                     | +---------+ |                               |
|                     +-------------+                               |
+------------------------------------------------------------------+
```

### Elasticsearch Indexing / Индексирование Elasticsearch

```json
// Index mapping for logs
PUT /logs-2026.01.12
{
  "mappings": {
    "properties": {
      "@timestamp": { "type": "date" },
      "level": { "type": "keyword" },
      "message": { "type": "text" },
      "service": { "type": "keyword" },
      "trace_id": { "type": "keyword" },
      "match_id": { "type": "keyword" },
      "host": { "type": "keyword" },
      "duration_ms": { "type": "float" },
      "error": {
        "properties": {
          "type": { "type": "keyword" },
          "message": { "type": "text" },
          "stack_trace": { "type": "text" }
        }
      }
    }
  },
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1,
    "index.lifecycle.name": "logs-policy"
  }
}
```

### Logstash Pipeline / Пайплайн Logstash

```ruby
# /etc/logstash/conf.d/pipeline.conf

input {
  beats {
    port => 5044
  }
}

filter {
  # Parse JSON logs
  json {
    source => "message"
    target => "parsed"
  }

  # Extract fields from parsed JSON
  mutate {
    rename => {
      "[parsed][level]" => "level"
      "[parsed][msg]" => "log_message"
      "[parsed][trace_id]" => "trace_id"
      "[parsed][match_id]" => "match_id"
    }
  }

  # Add processing timestamp
  date {
    match => ["[parsed][timestamp]", "ISO8601"]
    target => "@timestamp"
  }

  # Enrich with GeoIP for client logs
  if [client_ip] {
    geoip {
      source => "client_ip"
    }
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "logs-%{+YYYY.MM.dd}"
    ilm_enabled => true
    ilm_policy => "logs-policy"
  }
}
```

### Kibana Query Language (KQL) / Язык запросов Kibana

```
# Basic field queries
level: error
service: "video-processor"

# Wildcard and regex
message: *timeout*
match_id: /abc[0-9]+/

# Boolean operators
level: error AND service: video-processor
level: (error OR warn) AND NOT message: "health check"

# Range queries
duration_ms >= 1000
@timestamp >= "2026-01-12T00:00:00" AND @timestamp < "2026-01-13T00:00:00"

# Nested fields
error.type: "GPUMemoryError"

# Combined complex query
level: error AND service: video-processor AND duration_ms > 500
AND match_id: abc* AND NOT message: "retry successful"
```

---

## Grafana Loki Overview / Обзор Grafana Loki

### Architecture / Архитектура

```
+------------------------------------------------------------------+
|                        GRAFANA LOKI                               |
+------------------------------------------------------------------+
|                                                                   |
|  Log Sources          Loki Components              Visualization  |
|  +----------+        +---------------------+       +----------+   |
|  |App Logs  |        |                     |       |          |   |
|  +----+-----+        |    DISTRIBUTOR      |       | Grafana  |   |
|       |              |   (Load balance)    |       |          |   |
|       v              +----------+----------+       | LogQL    |   |
|  +----------+                   |                  | Explorer |   |
|  |Promtail  |-------------------+                  |          |   |
|  |  or      |                   v                  +----+-----+   |
|  |Fluent Bit|        +----------+----------+            |         |
|  +----------+        |                     |            |         |
|                      |     INGESTER        |<-----------+         |
|                      | (Write path, WAL)   |                      |
|                      +----------+----------+                      |
|                                 |                                 |
|                                 v                                 |
|                      +---------------------+                      |
|                      |   OBJECT STORAGE    |                      |
|                      | (S3, GCS, MinIO)    |                      |
|                      +----------+----------+                      |
|                                 |                                 |
|                                 v                                 |
|                      +---------------------+                      |
|                      |      QUERIER        |                      |
|                      |   (Read path)       |                      |
|                      +---------------------+                      |
|                                                                   |
+------------------------------------------------------------------+

Key Difference: Loki indexes ONLY labels, not log content!

ELK: Full-text index of all content -> High storage, fast search
Loki: Label index only -> Low storage, grep-like search
```

### Loki Labels / Метки Loki

```yaml
# Good labels (low cardinality)
labels:
  - job: video-processor
  - environment: production
  - level: error
  - host: worker-01

# Bad labels (high cardinality - AVOID!)
labels:
  - trace_id: 4bf92f3577b3...  # Millions of unique values!
  - user_id: 12345              # Too many users
  - request_id: uuid...         # Every request is unique
```

### LogQL Query Language / Язык запросов LogQL

```logql
# Stream selector (required)
{job="video-processor"}

# Label matchers
{job="video-processor", level="error"}
{job=~"video-.*"}                      # Regex match
{job!="healthcheck"}                   # Not equal

# Line filters (grep-like, applied AFTER label selection)
{job="video-processor"} |= "error"           # Contains
{job="video-processor"} != "health check"    # Does not contain
{job="video-processor"} |~ "match_id=abc.*"  # Regex match
{job="video-processor"} !~ "DEBUG|TRACE"     # Negative regex

# JSON parsing
{job="video-processor"}
  | json
  | level="error"
  | duration_ms > 1000

# Label extraction
{job="video-processor"}
  | json
  | line_format "{{.level}}: {{.message}} ({{.match_id}})"

# Aggregations
sum(rate({job="video-processor"} |= "error" [5m])) by (host)

# Count errors per minute
count_over_time({job="video-processor", level="error"}[1m])

# Top 5 hosts by error count
topk(5, sum by (host) (count_over_time({level="error"}[1h])))

# Log volume
sum(bytes_over_time({job="video-processor"}[1h])) by (level)
```

### Promtail Configuration / Конфигурация Promtail

```yaml
# /etc/promtail/config.yml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: containers
    static_configs:
      - targets:
          - localhost
        labels:
          job: video-processor
          __path__: /var/log/containers/*.log

    pipeline_stages:
      # Parse Docker JSON logs
      - json:
          expressions:
            output: log
            stream: stream
            timestamp: time

      # Parse application JSON from output
      - json:
          source: output
          expressions:
            level: level
            message: msg
            trace_id: trace_id
            match_id: match_id

      # Set labels from extracted fields
      - labels:
          level:
          match_id:

      # Set log line to message only
      - output:
          source: message

      # Drop debug logs in production
      - match:
          selector: '{level="debug"}'
          action: drop
```

---

## ELK vs Loki Comparison / Сравнение ELK и Loki

### Feature Comparison / Сравнение функций

| Feature | ELK Stack | Grafana Loki |
|---------|-----------|--------------|
| **Indexing** | Full-text all fields | Labels only |
| **Query Language** | KQL, Lucene, EQL | LogQL |
| **Storage Cost** | High (index + data) | Low (labels + compressed) |
| **Query Speed** | Very fast (indexed) | Fast for labels, grep for content |
| **Complexity** | High (JVM, cluster) | Low (single binary) |
| **Memory Usage** | High (heap for indexing) | Low |
| **Horizontal Scaling** | Complex (sharding) | Simple (stateless) |
| **Multi-tenancy** | Index-based | Native support |
| **Alerting** | Kibana Alerts | Grafana Alerting |
| **Visualization** | Kibana | Grafana |
| **Learning Curve** | Steep | Gentle (if know PromQL) |
| **APM Integration** | Elastic APM | OpenTelemetry |

### Cost Comparison / Сравнение стоимости

```
Scenario: 100 GB logs/day, 30-day retention

+------------------------------------------------------------------+
|                    RESOURCE REQUIREMENTS                          |
+------------------------------------------------------------------+
|                                                                   |
|  ELK STACK                          GRAFANA LOKI                  |
|  +------------------------+         +------------------------+    |
|  | Elasticsearch Cluster  |         | Loki (3 replicas)      |    |
|  | - 3 data nodes         |         | - 4 CPU, 8GB RAM each  |    |
|  | - 16 CPU, 64GB each    |         |                        |    |
|  | - 500GB SSD each       |         | Object Storage (S3)    |    |
|  +------------------------+         | - ~800GB (compressed)  |    |
|                                     +------------------------+    |
|  Storage: ~3TB (index + data)                                    |
|  Compression: ~3x                   Compression: ~10x            |
|                                                                   |
|  Monthly Cost (Cloud):              Monthly Cost (Cloud):        |
|  ~$2,000-4,000                      ~$500-800                    |
+------------------------------------------------------------------+
```

### When to Choose Each / Когда выбирать каждый

```
+------------------------------------------------------------------+
|                     DECISION MATRIX                               |
+------------------------------------------------------------------+
|                                                                   |
|  CHOOSE ELK WHEN:                  CHOOSE LOKI WHEN:             |
|  +------------------------+        +-------------------------+    |
|  | Complex log analytics  |        | Cost-sensitive          |    |
|  | needed                 |        |                         |    |
|  +------------------------+        +-------------------------+    |
|  | Full-text search is    |        | Label-based filtering   |    |
|  | critical               |        | is sufficient           |    |
|  +------------------------+        +-------------------------+    |
|  | Existing Elastic       |        | Already using Grafana   |    |
|  | expertise              |        | for metrics             |    |
|  +------------------------+        +-------------------------+    |
|  | Security/compliance    |        | Kubernetes-native       |    |
|  | requirements (SIEM)    |        | deployment              |    |
|  +------------------------+        +-------------------------+    |
|  | APM with Elastic APM   |        | OpenTelemetry for       |    |
|  |                        |        | tracing                 |    |
|  +------------------------+        +-------------------------+    |
|                                                                   |
+------------------------------------------------------------------+
```

---

## Structured Logging Best Practices / Лучшие практики структурированного логирования

### Python Implementation / Реализация на Python

```python
import structlog
import logging
from opentelemetry import trace

# Configure structlog
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Add trace context to all logs
def add_trace_context(logger, method_name, event_dict):
    span = trace.get_current_span()
    if span.is_recording():
        ctx = span.get_span_context()
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict

# Usage example
def process_match(match_id: str):
    log = logger.bind(match_id=match_id, service="video-processor")

    log.info("processing_started", stage="ingest")

    try:
        # Processing logic
        frames = stitch_frames(match_id)
        log.info("stitch_completed", frame_count=len(frames))

        detections = run_detection(frames)
        log.info("detection_completed",
                 detection_count=len(detections),
                 duration_ms=elapsed)

    except GPUMemoryError as e:
        log.error("processing_failed",
                  error_type="GPUMemoryError",
                  error_message=str(e),
                  gpu_memory_used=get_gpu_memory())
        raise
```

### Log Schema Standards / Стандарты схемы логов

```json
{
  "timestamp": "2026-01-12T14:30:00.123Z",
  "level": "error",
  "logger": "polyvision.video.processor",
  "message": "Failed to process video frame batch",

  "service": {
    "name": "video-processor",
    "version": "2.1.0",
    "environment": "production"
  },

  "trace": {
    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    "span_id": "00f067aa0ba902b7"
  },

  "context": {
    "match_id": "match_abc123",
    "organization_id": "org_xyz789",
    "stage": "detect",
    "batch_index": 15
  },

  "metrics": {
    "duration_ms": 1523,
    "frames_processed": 1000,
    "gpu_memory_mb": 14336
  },

  "error": {
    "type": "GPUMemoryError",
    "message": "CUDA out of memory",
    "stack_trace": "..."
  },

  "host": {
    "name": "gpu-worker-03",
    "ip": "10.0.1.45"
  }
}
```

### Common Pitfalls / Распространённые ошибки

| Pitfall | Problem | Solution |
|---------|---------|----------|
| **Unstructured logs** | Can't filter/aggregate | Always use JSON |
| **High cardinality labels** | Index explosion | Use labels for grouping only |
| **Missing trace IDs** | Can't correlate | Always include trace context |
| **Inconsistent field names** | Query complexity | Define schema, validate |
| **Logging secrets** | Security breach | Sanitize before logging |
| **Too verbose** | Storage costs | Use appropriate log levels |
| **No context** | Debugging difficulty | Include relevant IDs |

---

## Implementation Patterns / Паттерны реализации

### Centralized Logging with Loki / Централизованное логирование с Loki

```yaml
# docker-compose.yml
services:
  loki:
    image: grafana/loki:2.9.0
    ports:
      - "3100:3100"
    volumes:
      - ./loki-config.yaml:/etc/loki/local-config.yaml
      - loki-data:/loki
    command: -config.file=/etc/loki/local-config.yaml

  promtail:
    image: grafana/promtail:2.9.0
    volumes:
      - ./promtail-config.yaml:/etc/promtail/config.yaml
      - /var/log:/var/log:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
    command: -config.file=/etc/promtail/config.yaml

  grafana:
    image: grafana/grafana:10.0.0
    ports:
      - "3000:3000"
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana-datasources.yaml:/etc/grafana/provisioning/datasources/datasources.yaml
```

### Log-based Alerting / Алертинг на основе логов

```yaml
# Grafana alerting rule for logs
groups:
  - name: log-alerts
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate({job="video-processor", level="error"}[5m])) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate in video processor"
          description: "More than 10 errors per second for 5 minutes"

      - alert: ProcessingTimeout
        expr: |
          count_over_time(
            {job="video-processor"}
            |= "timeout"
            |= "processing"
            [5m]
          ) > 5
        for: 2m
        labels:
          severity: critical
```

---

## Связано с

- [[Three-Pillars]]
- [[Prometheus-Grafana]]
- [[Distributed-Tracing]]
- [[PV-Monitoring]]

## Ресурсы

1. Elasticsearch Documentation: https://www.elastic.co/guide/en/elasticsearch/reference/current/
2. Grafana Loki Documentation: https://grafana.com/docs/loki/latest/
3. LogQL Documentation: https://grafana.com/docs/loki/latest/logql/
4. Structlog Documentation: https://www.structlog.org/
5. "Logging Best Practices": https://www.datadoghq.com/blog/python-logging-best-practices/
6. ELK vs Loki Comparison: https://grafana.com/blog/2020/05/12/an-only-slightly-biased-comparison-of-loki-and-elasticsearch/
7. Promtail Configuration: https://grafana.com/docs/loki/latest/clients/promtail/configuration/
8. Kibana Query Language: https://www.elastic.co/guide/en/kibana/current/kuery-query.html

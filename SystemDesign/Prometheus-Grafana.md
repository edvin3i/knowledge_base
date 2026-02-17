---
tags:
  - system-design
  - observability
  - prometheus
  - grafana
created: 2026-02-17
---

# Prometheus и Grafana / Prometheus & Grafana: Metrics Mastery

## Что это

Prometheus — система мониторинга с pull-моделью и PromQL. Grafana — визуализация метрик. Ключевые концепции: типы метрик (Counter, Gauge, Histogram, Summary), PromQL (rate, histogram_quantile, aggregations), Alertmanager (routing, grouping, inhibition), recording rules, dashboard design, SLO/SLI.

---

## Introduction / Введение

Prometheus is an open-source monitoring system with a powerful query language (PromQL) and a pull-based metrics collection model. Grafana provides the visualization layer, transforming raw metrics into actionable dashboards.

Prometheus -- это система мониторинга с открытым исходным кодом, обладающая мощным языком запросов (PromQL) и pull-моделью сбора метрик. Grafana обеспечивает визуализацию, превращая сырые метрики в информативные дашборды.

---

## Prometheus Architecture / Архитектура Prometheus

```
+------------------------------------------------------------------+
|                      PROMETHEUS ECOSYSTEM                         |
+------------------------------------------------------------------+
|                                                                   |
|   TARGETS (Scrape)           PROMETHEUS SERVER                    |
|   +--------------+          +-------------------+                 |
|   | Application  |<---------|  Scrape Manager   |                 |
|   | /metrics     |   pull   +-------------------+                 |
|   +--------------+                   |                            |
|                                      v                            |
|   +--------------+          +-------------------+                 |
|   | Node Exporter|<---------|     TSDB          |                 |
|   +--------------+          | (Time Series DB)  |                 |
|                             +-------------------+                 |
|   +--------------+                   |                            |
|   | Pushgateway  |<--push            |                            |
|   |(short jobs)  |           +-------------------+                |
|   +--------------+           |   PromQL Engine   |                |
|                              +-------------------+                |
|   SERVICE DISCOVERY                  |                            |
|   +--------------+                   v                            |
|   | Kubernetes   |          +-------------------+                 |
|   | Consul       |          |   HTTP API        |<-----> Grafana  |
|   | DNS          |          +-------------------+                 |
|   +--------------+                   |                            |
|                                      v                            |
|                             +-------------------+                 |
|                             |  Alertmanager     |---> PagerDuty   |
|                             +-------------------+     Slack       |
|                                                       Email       |
+------------------------------------------------------------------+
```

### Key Components / Ключевые компоненты

| Component | Purpose | Description |
|-----------|---------|-------------|
| **Prometheus Server** | Core | Scrapes, stores, and queries metrics |
| **TSDB** | Storage | Time-series database with efficient compression |
| **Alertmanager** | Alerting | Routes, groups, and deduplicates alerts |
| **Pushgateway** | Batch jobs | Accepts pushed metrics from short-lived jobs |
| **Exporters** | Adapters | Expose metrics from third-party systems |

---

## PromQL Fundamentals / Основы PromQL

### Data Types / Типы данных

| Type | Description | Example |
|------|-------------|---------|
| **Instant Vector** | Single value per series at one time | `http_requests_total` |
| **Range Vector** | Multiple values per series over time | `http_requests_total[5m]` |
| **Scalar** | Single numeric value | `42` or `sum(...)` |
| **String** | Text (rarely used) | `"error"` |

### Basic Queries / Базовые запросы

```promql
# Select all time series with a metric name
http_requests_total

# Filter by label
http_requests_total{status="200"}

# Multiple label filters
http_requests_total{method="GET", status=~"2.."}

# Label matching operators
# =  : Exact match
# != : Not equal
# =~ : Regex match
# !~ : Negative regex match
http_requests_total{endpoint!="/health", status=~"5.."}
```

### Range Vectors and Functions / Диапазонные векторы и функции

```promql
# Rate: per-second increase over time range
rate(http_requests_total[5m])

# Increase: absolute increase over time range
increase(http_requests_total[1h])

# Average over time
avg_over_time(cpu_usage[10m])

# Histogram quantiles (P50, P95, P99)
histogram_quantile(0.99, rate(http_request_duration_bucket[5m]))
```

### Aggregation Operators / Операторы агрегации

```promql
# Sum all values
sum(http_requests_total)

# Sum by label (grouping)
sum by (service) (rate(http_requests_total[5m]))

# Sum without specific labels
sum without (instance) (rate(http_requests_total[5m]))

# Available aggregations:
# sum, avg, min, max, count, stddev, stdvar
# count_values, topk, bottomk, quantile
```

---

## Advanced PromQL / Продвинутый PromQL

### Binary Operations / Бинарные операции

```promql
# Arithmetic between vectors (matching labels)
node_memory_MemTotal_bytes - node_memory_MemFree_bytes

# Calculate error rate percentage
sum(rate(http_requests_total{status=~"5.."}[5m])) /
sum(rate(http_requests_total[5m])) * 100

# Vector matching with ignoring/on
sum by (service) (rate(http_requests_total[5m]))
  / ignoring(status) group_left
sum by (service) (rate(http_requests_total[5m]))
```

### Useful Patterns / Полезные паттерны

```promql
# 1. Request rate by endpoint
sum by (endpoint) (rate(http_requests_total[5m]))

# 2. Error budget consumption (SLO = 99.9%)
1 - (
  sum(rate(http_requests_total{status=~"2.."}[30d])) /
  sum(rate(http_requests_total[30d]))
) / (1 - 0.999)

# 3. P99 latency by service
histogram_quantile(0.99,
  sum by (service, le) (
    rate(http_request_duration_bucket[5m])
  )
)

# 4. Saturation (queue depth)
avg_over_time(task_queue_length[5m])

# 5. Apdex score (satisfied < 0.5s, tolerating < 2s)
(
  sum(rate(http_request_duration_bucket{le="0.5"}[5m])) +
  sum(rate(http_request_duration_bucket{le="2.0"}[5m]))
) / 2 / sum(rate(http_request_duration_count[5m]))
```

### Subqueries / Подзапросы

```promql
# Max rate over the last hour, sampled every minute
max_over_time(rate(http_requests_total[5m])[1h:1m])

# 95th percentile of the rate over time
quantile_over_time(0.95, rate(http_requests_total[5m])[1h:1m])
```

---

## Alerting with Prometheus / Алертинг с Prometheus

### Alert Rule Structure / Структура правил алертов

```yaml
# /etc/prometheus/rules/alerts.yml
groups:
  - name: http_alerts
    rules:
      - alert: HighErrorRate
        expr: |
          sum by (service) (rate(http_requests_total{status=~"5.."}[5m]))
          / sum by (service) (rate(http_requests_total[5m]))
          > 0.05
        for: 5m
        labels:
          severity: critical
          team: backend
        annotations:
          summary: "High error rate on {{ $labels.service }}"
          description: |
            Error rate is {{ printf "%.2f" $value }}%
            (threshold: 5%)
          runbook_url: https://wiki.example.com/runbooks/high-error-rate

      - alert: HighLatencyP99
        expr: |
          histogram_quantile(0.99,
            sum by (service, le) (rate(http_request_duration_bucket[5m]))
          ) > 1.0
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "P99 latency above 1s on {{ $labels.service }}"
```

### Alertmanager Configuration / Конфигурация Alertmanager

```yaml
# /etc/alertmanager/alertmanager.yml
global:
  resolve_timeout: 5m
  slack_api_url: 'https://hooks.slack.com/services/xxx'

route:
  receiver: 'default'
  group_by: ['alertname', 'service']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty-critical'
      continue: true
    - match:
        severity: warning
      receiver: 'slack-warnings'

receivers:
  - name: 'default'
    slack_configs:
      - channel: '#alerts'
        send_resolved: true

  - name: 'pagerduty-critical'
    pagerduty_configs:
      - service_key: '<pagerduty-key>'

  - name: 'slack-warnings'
    slack_configs:
      - channel: '#alerts-warnings'

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'service']
```

### Alert Lifecycle / Жизненный цикл алерта

```
                    +------------+
                    |  INACTIVE  |
                    +-----+------+
                          |
          expr evaluates true
                          |
                          v
                    +------------+
                    |  PENDING   |  (for duration)
                    +-----+------+
                          |
          duration elapsed
                          |
                          v
                    +------------+
                    |   FIRING   |-----> Alertmanager
                    +-----+------+
                          |
          expr evaluates false
                          |
                          v
                    +------------+
                    |  RESOLVED  |-----> Alertmanager
                    +------------+
```

---

## Grafana Dashboard Design / Дизайн дашбордов Grafana

### Dashboard Structure / Структура дашборда

```
+------------------------------------------------------------------+
|                     SERVICE OVERVIEW                              |
+------------------------------------------------------------------+
|  [Service Dropdown v]  [Time Range v]  [Refresh v]               |
+------------------------------------------------------------------+
|                                                                   |
|  +--------------------+  +--------------------+  +--------------+ |
|  |    REQUEST RATE    |  |    ERROR RATE      |  |   LATENCY    | |
|  |    1,234 req/s     |  |     0.12%          |  |  P99: 145ms  | |
|  |    (stat panel)    |  |    (stat panel)    |  | (stat panel) | |
|  +--------------------+  +--------------------+  +--------------+ |
|                                                                   |
|  +--------------------------------------------------------------+ |
|  |                   REQUEST RATE OVER TIME                     | |
|  |   ___                      ___                               | |
|  |  /   \    ___             /   \                              | |
|  | /     \__/   \___________/     \                             | |
|  |                                  (time series panel)         | |
|  +--------------------------------------------------------------+ |
|                                                                   |
|  +------------------------------+  +----------------------------+ |
|  |     LATENCY HEATMAP         |  |     ERROR BREAKDOWN        | |
|  |   Darker = Higher count     |  |     [Pie: 500, 502, 503]   | |
|  |   (heatmap panel)           |  |     (pie chart panel)      | |
|  +------------------------------+  +----------------------------+ |
|                                                                   |
+------------------------------------------------------------------+
```

### Panel Types / Типы панелей

| Panel Type | Use Case | Metric Type |
|------------|----------|-------------|
| **Stat** | Single important values | Current rate, error % |
| **Time Series** | Trends over time | Rate, gauge values |
| **Heatmap** | Distribution over time | Histogram buckets |
| **Table** | Detailed breakdowns | Top endpoints, errors |
| **Pie/Donut** | Proportional data | Error type breakdown |
| **Gauge** | Progress/thresholds | Resource utilization |
| **Bar Gauge** | Comparative values | Service comparison |

### Dashboard Best Practices / Лучшие практики дашбордов

```yaml
# Dashboard JSON structure principles
principles:
  - Use variables for service, environment, time range
  - Group related panels in rows
  - Put critical metrics at the top (above the fold)
  - Use consistent color schemes (red=bad, green=good)
  - Include links to relevant dashboards and runbooks
  - Add annotations for deployments and incidents

# Example variable definition
variables:
  - name: service
    type: query
    query: label_values(http_requests_total, service)
    refresh: on_time_range_change

  - name: environment
    type: custom
    options: ["production", "staging", "development"]
```

### Example Panel Configuration / Пример конфигурации панели

```json
{
  "title": "Request Rate by Endpoint",
  "type": "timeseries",
  "targets": [
    {
      "expr": "sum by (endpoint) (rate(http_requests_total{service=\"$service\"}[5m]))",
      "legendFormat": "{{ endpoint }}"
    }
  ],
  "fieldConfig": {
    "defaults": {
      "unit": "reqps",
      "thresholds": {
        "mode": "absolute",
        "steps": [
          {"color": "green", "value": null},
          {"color": "yellow", "value": 1000},
          {"color": "red", "value": 5000}
        ]
      }
    }
  }
}
```

---

## Recording Rules / Правила записи

Recording rules pre-compute expensive queries and store results as new time series.

```yaml
# /etc/prometheus/rules/recording.yml
groups:
  - name: http_recording
    interval: 30s
    rules:
      # Pre-compute request rate by service
      - record: service:http_requests:rate5m
        expr: sum by (service) (rate(http_requests_total[5m]))

      # Pre-compute error rate by service
      - record: service:http_errors:rate5m
        expr: |
          sum by (service) (rate(http_requests_total{status=~"5.."}[5m]))
          / sum by (service) (rate(http_requests_total[5m]))

      # Pre-compute P99 latency
      - record: service:http_latency:p99_5m
        expr: |
          histogram_quantile(0.99,
            sum by (service, le) (rate(http_request_duration_bucket[5m]))
          )

      # Pre-compute for SLO (30-day availability)
      - record: service:http_availability:ratio_30d
        expr: |
          sum by (service) (increase(http_requests_total{status=~"2.."}[30d]))
          / sum by (service) (increase(http_requests_total[30d]))
```

### Recording Rule Naming Convention / Соглашение об именовании

```
level:metric:operations

Examples:
- job:http_requests:rate5m          (job level aggregation)
- service:http_errors:ratio_5m      (service level, error ratio)
- instance:node_cpu:avg_idle_5m     (instance level, CPU)
```

---

## Best Practices / Лучшие практики

### Metric Naming / Именование метрик

```python
# Good naming
http_requests_total          # Counter (use _total suffix)
http_request_duration_seconds # Histogram (use base unit)
process_open_fds             # Gauge (no special suffix)

# Bad naming
requests                     # Too vague
httpRequests                 # Not snake_case
request_time_ms              # Use seconds, not milliseconds
```

### Label Guidelines / Рекомендации по меткам

| Do | Don't |
|----|-------|
| Use static labels | Use high-cardinality labels |
| `service="auth"` | `user_id="12345"` |
| `status_code="2xx"` | `request_id="uuid"` |
| Keep labels small | Put long strings in labels |

### Cardinality Control / Контроль кардинальности

```promql
# Check cardinality
count by (__name__) ({__name__=~".+"})

# Alert on high cardinality
count(http_requests_total) by (service) > 10000
```

### Retention and Federation / Хранение и федерация

```yaml
# Prometheus retention settings
storage:
  tsdb:
    retention.time: 15d
    retention.size: 50GB

# Federation for long-term storage
scrape_configs:
  - job_name: 'federate'
    scrape_interval: 1m
    honor_labels: true
    metrics_path: '/federate'
    params:
      'match[]':
        - '{job=~".+"}'
    static_configs:
      - targets: ['prometheus-short-term:9090']
```

---

## Связано с

- [[Three-Pillars]]
- [[Distributed-Tracing]]
- [[Log-Aggregation]]
- [[PV-Monitoring]]

## Ресурсы

1. Prometheus Official Documentation: https://prometheus.io/docs/
2. PromQL for Humans: https://timber.io/blog/promql-for-humans/
3. Grafana Dashboard Best Practices: https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/best-practices/
4. "Prometheus: Up & Running" by Brian Brazil (O'Reilly, 2018)
5. Robust Perception Blog: https://www.robustperception.io/blog/
6. Alerting Best Practices: https://prometheus.io/docs/practices/alerting/
7. Recording Rules: https://prometheus.io/docs/prometheus/latest/configuration/recording_rules/
8. Grafana Tutorials: https://grafana.com/tutorials/

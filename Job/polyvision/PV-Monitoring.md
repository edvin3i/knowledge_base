---
tags:
  - polyvision
  - system-design
  - observability
created: 2026-02-17
---

# Стек наблюдаемости Polyvision / Polyvision Observability Stack Decision

## Что это

Решение по стеку наблюдаемости Polyvision: Prometheus + Grafana (метрики), Grafana Loki (логи), Jaeger + OpenTelemetry (трейсы), Grafana Alerting + Alertmanager. GPU-метрики через DCGM exporter. SLO: API 99.9%, processing 99.5%, video delivery 99.99%. Четырёхфазный план реализации (8 недель).

---

## Executive Summary / Краткое резюме

This document defines the observability architecture for Polyvision's video processing platform. The decision focuses on enabling effective debugging of GPU-intensive pipelines, tracking processing jobs across services, and ensuring platform reliability.

**Selected Stack:**
- **Metrics:** Prometheus + Grafana
- **Logs:** Grafana Loki + OpenTelemetry
- **Traces:** Jaeger + OpenTelemetry (OTLP)
- **Alerting:** Grafana Alerting + Alertmanager

**Key Rationale:** Unified Grafana experience, cost-effective Loki for logs, OpenTelemetry for vendor-neutral instrumentation, and proven Prometheus for metrics in Kubernetes environments.

---

## System Context / Контекст системы

### Polyvision Architecture Overview / Обзор архитектуры Polyvision

```
+------------------------------------------------------------------+
|                    POLYVISION SYSTEM CONTEXT                      |
+------------------------------------------------------------------+
|                                                                   |
|  EDGE LAYER                API LAYER                GPU WORKERS   |
|  (Jetson)                  (FastAPI)               (CUDA)         |
|  +----------+              +----------+            +----------+   |
|  |Live      |              |Gateway   |            |Stitch    |   |
|  |Stream    |------------->|Auth      |----------->|Detect    |   |
|  |Detection |              |Catalog   |            |VCam      |   |
|  +----------+              +----------+            +----------+   |
|       |                         |                       |         |
|       v                         v                       v         |
|  +----------+              +----------+            +----------+   |
|  |RTMP      |              |PostgreSQL|            |MinIO     |   |
|  |Stream    |              |ClickHouse|            |Storage   |   |
|  +----------+              |Redis     |            +----------+   |
|                            +----------+                           |
|                                 |                                 |
|                                 v                                 |
|                            +----------+                           |
|                            |Celery    |                           |
|                            |Redpanda  |                           |
|                            +----------+                           |
|                                                                   |
+------------------------------------------------------------------+

Key Observability Challenges:
1. GPU processing latency and memory usage
2. Distributed job tracking (Celery + Redpanda)
3. Video pipeline throughput (frames/sec)
4. Multi-tenant isolation
5. Storage (MinIO) and database performance
```

### Critical Paths to Monitor / Критические пути для мониторинга

| Path | Components | Latency Target | Availability Target |
|------|------------|----------------|---------------------|
| **Live Stream** | Edge -> RTMP | < 500ms | 99.9% |
| **VOD Processing** | Ingest -> Package | < 30 min/match | 99.5% |
| **Analytics Query** | API -> ClickHouse | < 200ms P99 | 99.9% |
| **Video Delivery** | CDN -> Player | < 100ms TTFB | 99.99% |

---

## Observability Requirements / Требования к наблюдаемости

### Functional Requirements / Функциональные требования

```
+------------------------------------------------------------------+
|                    OBSERVABILITY REQUIREMENTS                     |
+------------------------------------------------------------------+
|                                                                   |
|  METRICS                                                         |
|  +------------------------------------------------------------+ |
|  | - GPU utilization per worker (CUDA metrics)                 | |
|  | - Frame processing rate (FPS)                               | |
|  | - Detection latency per tile batch                          | |
|  | - Job queue depth (Celery)                                  | |
|  | - Storage I/O (MinIO, ClickHouse)                           | |
|  | - HTTP request RED metrics per service                      | |
|  +------------------------------------------------------------+ |
|                                                                   |
|  LOGS                                                            |
|  +------------------------------------------------------------+ |
|  | - Structured JSON logs with trace context                   | |
|  | - Error aggregation by type and service                     | |
|  | - Processing stage transitions                              | |
|  | - GPU memory allocation events                              | |
|  +------------------------------------------------------------+ |
|                                                                   |
|  TRACES                                                          |
|  +------------------------------------------------------------+ |
|  | - End-to-end job processing (Ingest -> Package)             | |
|  | - Cross-service API calls                                   | |
|  | - Celery task chains                                        | |
|  | - Database query tracing                                    | |
|  +------------------------------------------------------------+ |
|                                                                   |
+------------------------------------------------------------------+
```

### Non-Functional Requirements / Нефункциональные требования

| Requirement | Target | Rationale |
|-------------|--------|-----------|
| **Retention** | 15 days hot, 90 days cold | Incident analysis window |
| **Ingestion Rate** | 100k metrics/sec | GPU workers + API services |
| **Log Volume** | ~50 GB/day | Processing logs, structured |
| **Query Latency** | < 5s for dashboards | Developer productivity |
| **Cost** | < $500/month (self-hosted) | Startup budget |

---

## Stack Selection / Выбор стека

### Decision Matrix / Матрица решений

```
+------------------------------------------------------------------+
|                     STACK COMPARISON                              |
+------------------------------------------------------------------+
|                                                                   |
|  COMPONENT     OPTION A           OPTION B          SELECTED     |
|  +----------+-----------------+-----------------+---------------+ |
|  | Metrics  | Prometheus      | InfluxDB        | Prometheus   | |
|  |          | + Grafana       | + Chronograf    | + Grafana    | |
|  +----------+-----------------+-----------------+---------------+ |
|  | Logs     | ELK Stack       | Grafana Loki    | Grafana Loki | |
|  |          | (Elastic)       | + Promtail      |              | |
|  +----------+-----------------+-----------------+---------------+ |
|  | Traces   | Elastic APM     | Jaeger +        | Jaeger +     | |
|  |          |                 | OpenTelemetry   | OTel         | |
|  +----------+-----------------+-----------------+---------------+ |
|  | Alerting | Elastic Alerts  | Grafana         | Grafana      | |
|  |          |                 | Alerting        | Alerting     | |
|  +----------+-----------------+-----------------+---------------+ |
|                                                                   |
+------------------------------------------------------------------+
```

### Selection Rationale / Обоснование выбора

**Prometheus + Grafana (Metrics):**
- Native Kubernetes integration
- Proven GPU monitoring with DCGM exporter
- PromQL is industry standard
- Large ecosystem of exporters

**Grafana Loki (Logs):**
- 10x lower storage cost than ELK
- Native Grafana integration (single pane)
- LogQL similar to PromQL
- Sufficient for label-based queries

**Jaeger + OpenTelemetry (Traces):**
- OpenTelemetry is vendor-neutral standard
- Jaeger integrates with Grafana
- Tail-based sampling in OTel Collector
- ClickHouse backend for long-term storage

### Final Architecture / Финальная архитектура

```
+------------------------------------------------------------------+
|               POLYVISION OBSERVABILITY STACK                      |
+------------------------------------------------------------------+
|                                                                   |
|  SERVICES                    COLLECTION                          |
|  +----------+               +----------------+                    |
|  |API       |--OTLP-------->|                |                    |
|  |Services  |               | OpenTelemetry  |                    |
|  +----------+               | Collector      |                    |
|                             |                |                    |
|  +----------+               | - Metrics      |----> Prometheus    |
|  |GPU       |--OTLP-------->| - Traces       |----> Jaeger        |
|  |Workers   |               | - Logs         |----> Loki          |
|  +----------+               +----------------+                    |
|                                    |                              |
|  +----------+                      |                              |
|  |Celery    |--OTLP----------------+                              |
|  |Workers   |                                                     |
|  +----------+                                                     |
|                                                                   |
|  +----------+               +----------------+                    |
|  |DCGM      |--Prometheus-->|   Prometheus   |                    |
|  |Exporter  |   scrape      |                |                    |
|  +----------+               +----------------+                    |
|                                    |                              |
|  +----------+                      |                              |
|  |Node      |--Prometheus----------+                              |
|  |Exporter  |   scrape                                            |
|  +----------+                      |                              |
|                                    v                              |
|                             +----------------+                    |
|                             |    GRAFANA     |                    |
|                             |                |                    |
|                             | - Dashboards   |                    |
|                             | - Alerting     |                    |
|                             | - Explore      |                    |
|                             +----------------+                    |
|                                                                   |
+------------------------------------------------------------------+
```

---

## Metrics Strategy / Стратегия метрик

### GPU Worker Metrics / Метрики GPU воркеров

```python
from prometheus_client import Counter, Histogram, Gauge, Info

# Processing metrics
frames_processed = Counter(
    'polyvision_frames_processed_total',
    'Total frames processed',
    ['worker', 'stage', 'match_id']
)

processing_duration = Histogram(
    'polyvision_processing_duration_seconds',
    'Processing duration by stage',
    ['stage'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

# GPU metrics (via DCGM or pynvml)
gpu_memory_used = Gauge(
    'polyvision_gpu_memory_used_bytes',
    'GPU memory used',
    ['gpu_id', 'worker']
)

gpu_utilization = Gauge(
    'polyvision_gpu_utilization_percent',
    'GPU utilization percentage',
    ['gpu_id', 'worker']
)

# Tile batch metrics
tile_batch_size = Histogram(
    'polyvision_tile_batch_size',
    'Tiles per batch',
    ['mode'],
    buckets=[1, 3, 6, 9, 12, 15, 18]
)

detection_count = Counter(
    'polyvision_detections_total',
    'Total detections',
    ['class', 'match_id']
)
```

### API Service Metrics / Метрики API сервисов

```python
# RED metrics for FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

instrumentator = Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_respect_env_var=True,
    excluded_handlers=["/health", "/ready", "/metrics"]
)

instrumentator.instrument(app).expose(app, include_in_schema=False)

# Custom business metrics
matches_uploaded = Counter(
    'polyvision_matches_uploaded_total',
    'Total matches uploaded',
    ['organization_id']
)

processing_jobs_queued = Gauge(
    'polyvision_processing_jobs_queued',
    'Jobs waiting in queue',
    ['stage']
)

processing_jobs_running = Gauge(
    'polyvision_processing_jobs_running',
    'Jobs currently processing',
    ['stage', 'worker']
)
```

### Key Dashboard Panels / Ключевые панели дашборда

```
+------------------------------------------------------------------+
|                   GPU PROCESSING DASHBOARD                        |
+------------------------------------------------------------------+
|                                                                   |
|  Row 1: Overview Stats                                           |
|  +----------------+ +----------------+ +----------------+         |
|  | Jobs Running   | | Jobs Queued    | | Avg Duration   |         |
|  |      12        | |      47        | |    8.5 min     |         |
|  +----------------+ +----------------+ +----------------+         |
|                                                                   |
|  Row 2: Processing Performance                                   |
|  +------------------------------------------------------+        |
|  | Frames/sec by Worker                                 |        |
|  | worker-01: ████████████████████ 1200                 |        |
|  | worker-02: ██████████████████ 1100                   |        |
|  | worker-03: ██████████ 600 (degraded)                 |        |
|  +------------------------------------------------------+        |
|                                                                   |
|  Row 3: GPU Resources                                            |
|  +---------------------------+ +---------------------------+      |
|  | GPU Memory Usage          | | GPU Utilization           |      |
|  |   ___    ____             | |   ----    ----            |      |
|  |  /   \__/    \___         | |  /    \  /    \           |      |
|  | /                 \       | | /      \/      \          |      |
|  +---------------------------+ +---------------------------+      |
|                                                                   |
|  Row 4: Stage Latency                                            |
|  +------------------------------------------------------+        |
|  | P99 Duration by Stage (heatmap)                      |        |
|  | stitch  ▓▓▓▓▓░░░░░░░░░░░░░░░ 2.1s                   |        |
|  | detect  ▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░ 5.2s                   |        |
|  | vcam    ▓▓▓▓▓▓▓▓░░░░░░░░░░░░ 3.1s                   |        |
|  +------------------------------------------------------+        |
|                                                                   |
+------------------------------------------------------------------+
```

---

## SLIs and SLOs / SLI и SLO

### Service Level Indicators / Индикаторы уровня сервиса

```yaml
# SLI Definitions
slis:
  # API Availability
  - name: api_availability
    description: "Successful API responses"
    metric: |
      sum(rate(http_requests_total{status=~"2.."}[5m]))
      / sum(rate(http_requests_total[5m]))

  # API Latency
  - name: api_latency_p99
    description: "99th percentile API response time"
    metric: |
      histogram_quantile(0.99,
        sum by (le) (rate(http_request_duration_seconds_bucket[5m]))
      )

  # Processing Success Rate
  - name: processing_success_rate
    description: "Successfully processed matches"
    metric: |
      sum(rate(polyvision_jobs_completed_total{status="success"}[1h]))
      / sum(rate(polyvision_jobs_completed_total[1h]))

  # Processing Duration
  - name: processing_duration_p95
    description: "95th percentile match processing time"
    metric: |
      histogram_quantile(0.95,
        sum by (le) (rate(polyvision_processing_duration_seconds_bucket[1h]))
      )

  # Video Delivery
  - name: video_delivery_availability
    description: "Successful video segment deliveries"
    metric: |
      sum(rate(polyvision_video_requests_total{status="success"}[5m]))
      / sum(rate(polyvision_video_requests_total[5m]))

  # GPU Worker Health
  - name: gpu_worker_availability
    description: "GPU workers healthy and processing"
    metric: |
      count(up{job="gpu-workers"} == 1)
      / count(up{job="gpu-workers"})
```

### Service Level Objectives / Цели уровня сервиса

| SLO | Target | Window | Error Budget |
|-----|--------|--------|--------------|
| **API Availability** | 99.9% | 30 days | 43.2 min/month |
| **API Latency P99** | < 500ms | 30 days | - |
| **Processing Success** | 99.5% | 7 days | 0.5% failures |
| **Processing Duration P95** | < 30 min | 7 days | - |
| **Video Delivery** | 99.99% | 30 days | 4.3 min/month |
| **GPU Workers Available** | 95% | 24 hours | 1.2 hours/day |

### Error Budget Policy / Политика бюджета ошибок

```yaml
error_budget_policy:
  thresholds:
    - level: normal
      budget_remaining: "> 50%"
      actions:
        - continue_normal_development
        - allow_risky_deployments

    - level: warning
      budget_remaining: "25% - 50%"
      actions:
        - reduce_deployment_frequency
        - prioritize_reliability_work
        - increase_monitoring

    - level: critical
      budget_remaining: "< 25%"
      actions:
        - freeze_feature_deployments
        - all_hands_on_reliability
        - postmortem_required_for_incidents

    - level: exhausted
      budget_remaining: "0%"
      actions:
        - emergency_freeze
        - executive_escalation
        - mandatory_reliability_sprint
```

---

## Alerting Strategy / Стратегия алертинга

### Alert Hierarchy / Иерархия алертов

```
+------------------------------------------------------------------+
|                      ALERT PYRAMID                                |
+------------------------------------------------------------------+
|                                                                   |
|                         /\                                        |
|                        /  \         PAGE (Critical)               |
|                       /    \        - Service down                |
|                      / P1   \       - SLO breach                  |
|                     /--------\      - Data loss risk              |
|                    /          \                                   |
|                   /    P2      \    URGENT (Warning)              |
|                  /              \   - Degraded performance        |
|                 /----------------\  - Error rate spike            |
|                /                  \ - Approaching limits          |
|               /        P3          \                              |
|              /                      \ TICKET (Low)                |
|             /------------------------\ - Anomalies                |
|            /            P4            \ - Capacity planning       |
|           /------------------------------\                        |
|          /              INFO              \ NOTIFY                |
|         /----------------------------------\ - Deployments        |
|                                               - Autoscaling       |
+------------------------------------------------------------------+
```

### Alert Rules / Правила алертов

```yaml
# /etc/prometheus/rules/polyvision-alerts.yml
groups:
  - name: polyvision.api
    rules:
      # P1: API Down
      - alert: APIServiceDown
        expr: up{job="api-gateway"} == 0
        for: 1m
        labels:
          severity: critical
          team: platform
        annotations:
          summary: "API Gateway is down"
          runbook: "https://wiki.polyvision.io/runbooks/api-down"

      # P1: High Error Rate
      - alert: APIHighErrorRate
        expr: |
          sum(rate(http_requests_total{status=~"5.."}[5m]))
          / sum(rate(http_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
          team: backend
        annotations:
          summary: "API error rate above 5%"
          description: "Current rate: {{ $value | humanizePercentage }}"

      # P2: High Latency
      - alert: APIHighLatency
        expr: |
          histogram_quantile(0.99,
            sum by (le) (rate(http_request_duration_seconds_bucket[5m]))
          ) > 1.0
        for: 10m
        labels:
          severity: warning
          team: backend
        annotations:
          summary: "API P99 latency above 1s"

  - name: polyvision.processing
    rules:
      # P1: Processing Pipeline Stalled
      - alert: ProcessingPipelineStalled
        expr: |
          increase(polyvision_jobs_completed_total[30m]) == 0
          AND polyvision_processing_jobs_queued > 0
        for: 15m
        labels:
          severity: critical
          team: video
        annotations:
          summary: "Processing pipeline stalled"

      # P2: GPU Worker Down
      - alert: GPUWorkerDown
        expr: up{job="gpu-workers"} == 0
        for: 5m
        labels:
          severity: warning
          team: infrastructure
        annotations:
          summary: "GPU worker {{ $labels.instance }} is down"

      # P2: GPU Memory Critical
      - alert: GPUMemoryCritical
        expr: |
          polyvision_gpu_memory_used_bytes
          / polyvision_gpu_memory_total_bytes > 0.95
        for: 5m
        labels:
          severity: warning
          team: video
        annotations:
          summary: "GPU memory above 95% on {{ $labels.worker }}"

      # P3: Processing Queue Growing
      - alert: ProcessingQueueGrowing
        expr: |
          polyvision_processing_jobs_queued > 100
          AND delta(polyvision_processing_jobs_queued[30m]) > 50
        for: 30m
        labels:
          severity: warning
          team: video
        annotations:
          summary: "Processing queue growing rapidly"

  - name: polyvision.storage
    rules:
      # P1: ClickHouse Down
      - alert: ClickHouseDown
        expr: up{job="clickhouse"} == 0
        for: 2m
        labels:
          severity: critical
          team: data
        annotations:
          summary: "ClickHouse is down"

      # P2: MinIO High Latency
      - alert: MinIOHighLatency
        expr: |
          histogram_quantile(0.99, rate(minio_s3_requests_duration_seconds_bucket[5m])) > 2.0
        for: 10m
        labels:
          severity: warning
          team: infrastructure
```

### Alertmanager Routing / Маршрутизация Alertmanager

```yaml
# /etc/alertmanager/alertmanager.yml
global:
  resolve_timeout: 5m
  slack_api_url: 'https://hooks.slack.com/services/xxx'

route:
  receiver: 'default-slack'
  group_by: ['alertname', 'team']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    # Critical -> PagerDuty + Slack
    - match:
        severity: critical
      receiver: 'pagerduty-critical'
      continue: true

    # Team-specific routing
    - match:
        team: video
      receiver: 'slack-video-team'

    - match:
        team: platform
      receiver: 'slack-platform-team'

receivers:
  - name: 'default-slack'
    slack_configs:
      - channel: '#alerts-polyvision'
        send_resolved: true
        title: '{{ .Status | toUpper }}: {{ .CommonLabels.alertname }}'
        text: '{{ .CommonAnnotations.summary }}'

  - name: 'pagerduty-critical'
    pagerduty_configs:
      - service_key: '<pagerduty-integration-key>'
        severity: critical

  - name: 'slack-video-team'
    slack_configs:
      - channel: '#video-team-alerts'
        send_resolved: true

  - name: 'slack-platform-team'
    slack_configs:
      - channel: '#platform-team-alerts'
        send_resolved: true

inhibit_rules:
  # If service is down, suppress high latency alerts
  - source_match:
      alertname: 'APIServiceDown'
    target_match:
      alertname: 'APIHighLatency'
    equal: ['service']
```

---

## Implementation Plan / План реализации

### Phase 1: Foundation (Week 1-2) / Фаза 1: Фундамент

```
Tasks:
[ ] Deploy Prometheus with basic scrape configs
[ ] Deploy Grafana with Prometheus datasource
[ ] Deploy Loki + Promtail for log collection
[ ] Deploy OTel Collector for centralized telemetry
[ ] Configure DCGM exporter for GPU metrics
[ ] Create basic service health dashboard
```

### Phase 2: Instrumentation (Week 3-4) / Фаза 2: Инструментирование

```
Tasks:
[ ] Add OTel SDK to all Python services
[ ] Instrument FastAPI with auto-instrumentation
[ ] Add manual spans for GPU processing stages
[ ] Configure structured logging with trace context
[ ] Instrument Celery tasks with context propagation
[ ] Add business metrics (matches, jobs, detections)
```

### Phase 3: Dashboards & Alerts (Week 5-6) / Фаза 3: Дашборды и алерты

```
Tasks:
[ ] Create GPU Processing dashboard
[ ] Create API Performance dashboard
[ ] Create Storage & Database dashboard
[ ] Define SLI/SLO recording rules
[ ] Configure Alertmanager routing
[ ] Set up on-call rotation with PagerDuty
```

### Phase 4: Optimization (Week 7-8) / Фаза 4: Оптимизация

```
Tasks:
[ ] Configure tail-based sampling in OTel Collector
[ ] Set up log retention policies (15d hot, 90d cold)
[ ] Create runbooks for common alerts
[ ] Load test observability stack
[ ] Document troubleshooting workflows
[ ] Train team on new tools
```

---

## Связано с

- [[Three-Pillars]]
- [[Prometheus-Grafana]]
- [[Distributed-Tracing]]
- [[Log-Aggregation]]
- [[PV-Networking]]
- [[PV-Security]]

## Ресурсы

1. Polyvision Architecture Documentation: /docs/backend-architecture.md
2. Google SRE Workbook: https://sre.google/workbook/implementing-slos/
3. NVIDIA DCGM Exporter: https://github.com/NVIDIA/dcgm-exporter
4. OpenTelemetry Python: https://opentelemetry.io/docs/languages/python/
5. Grafana Loki Best Practices: https://grafana.com/docs/loki/latest/best-practices/
6. Prometheus Alerting Best Practices: https://prometheus.io/docs/practices/alerting/
7. SLO Fundamentals: https://cloud.google.com/blog/products/devops-sre/sre-fundamentals-slis-slas-and-slos
8. Error Budget Policy: https://sre.google/workbook/error-budget-policy/

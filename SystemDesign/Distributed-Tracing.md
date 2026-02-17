---
tags:
  - system-design
  - observability
  - opentelemetry
  - jaeger
created: 2026-02-17
---

# Распределённая трассировка / Distributed Tracing: OpenTelemetry & Jaeger

## Что это

Распределённая трассировка -- отслеживание пути запроса через микросервисы. OpenTelemetry (OTel) -- стандарт сбора телеметрии (traces, metrics, logs). Jaeger -- бэкенд хранения и визуализации трейсов. Ключевые концепции: spans, trace_id, W3C TraceContext, context propagation, sampling (head-based, tail-based), OTel Collector.

---

## Introduction / Введение

Distributed tracing provides visibility into request flows across microservices. When a user action triggers calls to 10+ services, tracing shows the complete path, timing, and failures.

Распределённая трассировка обеспечивает видимость потоков запросов между микросервисами. Когда действие пользователя вызывает обращения к 10+ сервисам, трассировка показывает полный путь, тайминги и ошибки.

---

## Distributed Tracing Concepts / Концепции распределённой трассировки

### Trace Model / Модель трассировки

```
TRACE: End-to-end request journey (identified by trace_id)

+------------------------------------------------------------------+
|                         TRACE (trace_id)                          |
+------------------------------------------------------------------+
|                                                                   |
|  SPAN A: API Gateway (root span)                                 |
|  +=============================================================+ |
|  | span_id: aaaa  |  parent: none  |  duration: 250ms          | |
|  +=============================================================+ |
|       |                                                           |
|       +---> SPAN B: Auth Service                                 |
|       |    +==================================================+  |
|       |    | span_id: bbbb  |  parent: aaaa  |  duration: 45ms|  |
|       |    +==================================================+  |
|       |                                                           |
|       +---> SPAN C: Video Processor                              |
|            +==================================================+  |
|            | span_id: cccc  |  parent: aaaa  |  duration: 180ms| |
|            +==================================================+  |
|                 |                                                 |
|                 +---> SPAN D: GPU Worker                         |
|                      +=========================================+ |
|                      | span_id: dddd  |  parent: cccc  | 150ms | |
|                      +=========================================+ |
|                                                                   |
+------------------------------------------------------------------+

Timeline View:
|----SPAN A (API Gateway)-----------------------------------------|
     |--SPAN B (Auth)--|
                        |----SPAN C (Video Processor)-------------|
                             |----SPAN D (GPU Worker)---------|
0ms                        50ms                            200ms  250ms
```

### Span Anatomy / Анатомия спана

```
+------------------------------------------------------------------+
|                           SPAN                                    |
+------------------------------------------------------------------+
| trace_id:      4bf92f3577b34da6a3ce929d0e0e4736                  |
| span_id:       00f067aa0ba902b7                                  |
| parent_id:     7b7b7b7b7b7b7b7b (null for root)                  |
| operation:     POST /api/matches/{id}/process                    |
+------------------------------------------------------------------+
| timing:                                                          |
|   start_time:  2026-01-12T14:30:00.000Z                         |
|   end_time:    2026-01-12T14:30:00.245Z                         |
|   duration:    245ms                                             |
+------------------------------------------------------------------+
| status:        OK | ERROR                                        |
| kind:          SERVER | CLIENT | PRODUCER | CONSUMER | INTERNAL |
+------------------------------------------------------------------+
| attributes:                                                      |
|   http.method:     POST                                          |
|   http.url:        /api/matches/abc123/process                   |
|   http.status:     200                                           |
|   match_id:        abc123                                        |
|   processing.stage: stitch                                       |
+------------------------------------------------------------------+
| events:                                                          |
|   [14:30:00.100] Started GPU processing                         |
|   [14:30:00.200] Completed stitch operation                     |
+------------------------------------------------------------------+
| links:                                                           |
|   - trace_id: 5bf92f..., span_id: 11f067... (batch job)         |
+------------------------------------------------------------------+
```

---

## OpenTelemetry Overview / Обзор OpenTelemetry

OpenTelemetry (OTel) is the industry-standard framework for collecting telemetry data (traces, metrics, logs).

### Architecture / Архитектура

```
+------------------------------------------------------------------+
|                     OPENTELEMETRY ARCHITECTURE                    |
+------------------------------------------------------------------+
|                                                                   |
|  APPLICATION                      OTEL COLLECTOR                  |
|  +------------------+            +---------------------+          |
|  |                  |            |                     |          |
|  |  +------------+  |   OTLP     |  +--------------+  |          |
|  |  | OTel SDK   |--+----------->|  | Receivers    |  |          |
|  |  +------------+  |            |  +--------------+  |          |
|  |       |          |            |         |          |          |
|  |  +------------+  |            |  +--------------+  |          |
|  |  | Auto-Instr |  |            |  | Processors   |  |          |
|  |  +------------+  |            |  +--------------+  |          |
|  |       |          |            |         |          |          |
|  |  +------------+  |            |  +--------------+  |          |
|  |  | Manual     |  |            |  | Exporters    |  |          |
|  |  | Spans      |  |            |  +--------------+  |          |
|  |  +------------+  |            |         |          |          |
|  +------------------+            +---------+---------+           |
|                                            |                      |
|                      +---------------------+---------------------+ |
|                      |                     |                     | |
|                      v                     v                     v |
|               +----------+          +----------+          +------+ |
|               | Jaeger   |          | Zipkin   |          | ...  | |
|               +----------+          +----------+          +------+ |
+------------------------------------------------------------------+
```

### OTel Components / Компоненты OTel

| Component | Description | Languages |
|-----------|-------------|-----------|
| **API** | Vendor-neutral interfaces | Python, Go, Java, JS, .NET, Rust |
| **SDK** | Implementation of API | All supported languages |
| **Collector** | Receives, processes, exports | Binary (Go) |
| **Auto-instrumentation** | Zero-code instrumentation | Python, Java, .NET |

---

## Instrumentation / Инструментирование

### Python Auto-Instrumentation / Авто-инструментирование Python

```bash
# Install packages
pip install opentelemetry-api opentelemetry-sdk
pip install opentelemetry-instrumentation-fastapi
pip install opentelemetry-instrumentation-httpx
pip install opentelemetry-exporter-otlp

# Auto-instrument at startup
opentelemetry-instrument \
  --service_name video-processor \
  --traces_exporter otlp \
  --metrics_exporter otlp \
  --exporter_otlp_endpoint http://otel-collector:4317 \
  python app.py
```

### Manual Instrumentation / Ручное инструментирование

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

# Configure tracer provider
resource = Resource.create({
    "service.name": "video-processor",
    "service.version": "1.2.0",
    "deployment.environment": "production"
})

provider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="http://otel-collector:4317"))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

# Get tracer
tracer = trace.get_tracer(__name__)

# Create spans
@tracer.start_as_current_span("process_video")
def process_video(match_id: str) -> ProcessingResult:
    span = trace.get_current_span()

    # Add attributes
    span.set_attribute("match_id", match_id)
    span.set_attribute("processing.type", "full")

    # Add event
    span.add_event("Started video processing", {
        "video.resolution": "3856x2180",
        "video.fps": 60
    })

    try:
        with tracer.start_as_current_span("stitch_frames") as stitch_span:
            stitch_span.set_attribute("stitch.mode", "lut_based")
            result = stitch_service.process(match_id)

        with tracer.start_as_current_span("detect_objects") as detect_span:
            detect_span.set_attribute("detect.model", "yolov8")
            detections = detector.run(result.panorama)

        span.set_status(trace.StatusCode.OK)
        return ProcessingResult(success=True)

    except Exception as e:
        span.set_status(trace.StatusCode.ERROR, str(e))
        span.record_exception(e)
        raise
```

### Span Context / Контекст спана

```python
from opentelemetry import trace, context
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

# Extract context from incoming request (server side)
propagator = TraceContextTextMapPropagator()

def handle_request(request):
    ctx = propagator.extract(carrier=request.headers)
    with trace.get_tracer(__name__).start_as_current_span(
        "handle_request",
        context=ctx,
        kind=trace.SpanKind.SERVER
    ):
        # Process request
        pass

# Inject context into outgoing request (client side)
def call_downstream_service(url: str, data: dict):
    headers = {}
    propagator.inject(headers)  # Adds traceparent header

    with trace.get_tracer(__name__).start_as_current_span(
        "call_downstream",
        kind=trace.SpanKind.CLIENT
    ):
        response = httpx.post(url, json=data, headers=headers)
        return response
```

---

## Context Propagation / Распространение контекста

### W3C Trace Context / Контекст трассировки W3C

```
HTTP Headers:

traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
             |  |                                |                  |
             |  |                                |                  +-- Flags (01 = sampled)
             |  |                                +-- Parent Span ID (16 hex)
             |  +-- Trace ID (32 hex)
             +-- Version (00)

tracestate: vendor1=value1,vendor2=value2
            (optional vendor-specific data)
```

### Propagation Flow / Поток распространения

```
+------------------------------------------------------------------+
|                     CONTEXT PROPAGATION                           |
+------------------------------------------------------------------+
|                                                                   |
|  Client                         Server A                          |
|  +-----+                       +--------+                         |
|  |     |  traceparent: 00-abc-111-01    |                         |
|  |     |----------------------------->  |                         |
|  |     |                       | Extract context                  |
|  |     |                       | Create child span (222)          |
|  +-----+                       +--------+                         |
|                                    |                               |
|                                    | traceparent: 00-abc-222-01   |
|                                    v                               |
|                               +--------+                          |
|                               | Server B                          |
|                               | Extract context                   |
|                               | Create child span (333)           |
|                               +--------+                          |
|                                    |                               |
|                                    | Message queue (Kafka)        |
|                                    | Header: traceparent          |
|                                    v                               |
|                               +--------+                          |
|                               | Worker C                          |
|                               | Extract from message              |
|                               | Create child span (444)           |
|                               +--------+                          |
|                                                                   |
+------------------------------------------------------------------+
```

### Cross-Service Context / Контекст между сервисами

```python
# Celery task with context propagation
from opentelemetry import trace
from opentelemetry.propagate import inject, extract

@celery_app.task(bind=True)
def process_video_task(self, match_id: str, trace_context: dict):
    # Extract parent context
    ctx = extract(trace_context)

    with trace.get_tracer(__name__).start_as_current_span(
        "process_video_task",
        context=ctx,
        kind=trace.SpanKind.CONSUMER
    ):
        # Processing logic
        pass

# Calling the task with context
def enqueue_processing(match_id: str):
    trace_context = {}
    inject(trace_context)  # Inject current context

    process_video_task.delay(match_id, trace_context)
```

---

## Jaeger Architecture / Архитектура Jaeger

```
+------------------------------------------------------------------+
|                       JAEGER ARCHITECTURE                         |
+------------------------------------------------------------------+
|                                                                   |
|  Services              Collector            Storage               |
|  +--------+           +---------+          +----------+           |
|  | App 1  |--+        |         |          |          |           |
|  +--------+  |  OTLP  |  Jaeger |  Write   |Cassandra |           |
|              +------->| Collector|--------->|   or     |           |
|  +--------+  |        |         |          |Elasticsearch          |
|  | App 2  |--+        +---------+          |   or     |           |
|  +--------+  |             |               |ClickHouse |           |
|              |             | Sampling      +----------+           |
|  +--------+  |             | Config             |                  |
|  | App 3  |--+             v                    |                  |
|  +--------+        +-----------+                | Read             |
|                    | Remote    |                |                  |
|                    | Sampler   |                v                  |
|                    +-----------+           +---------+             |
|                                           | Jaeger  |             |
|                                           | Query   |<---> UI     |
|                                           +---------+             |
|                                                                   |
+------------------------------------------------------------------+

Deployment Modes:
+------------------+  +-------------------+  +-------------------+
| ALL-IN-ONE       |  | SIMPLE PRODUCTION |  | SCALABLE          |
| (Development)    |  | (Small scale)     |  | (Large scale)     |
+------------------+  +-------------------+  +-------------------+
| Single binary    |  | Collector +       |  | Multiple          |
| In-memory        |  | Query + Storage   |  | collectors behind |
| No persistence   |  | Single storage    |  | load balancer     |
+------------------+  +-------------------+  +-------------------+
```

### Jaeger Query API / API запросов Jaeger

```python
import requests

JAEGER_URL = "http://jaeger-query:16686"

# Find traces by service and operation
def find_traces(service: str, operation: str = None, limit: int = 20):
    params = {
        "service": service,
        "limit": limit,
        "lookback": "1h"
    }
    if operation:
        params["operation"] = operation

    response = requests.get(f"{JAEGER_URL}/api/traces", params=params)
    return response.json()["data"]

# Get specific trace
def get_trace(trace_id: str):
    response = requests.get(f"{JAEGER_URL}/api/traces/{trace_id}")
    return response.json()["data"][0]

# Find traces with specific tags
def find_traces_by_tag(service: str, tag_key: str, tag_value: str):
    params = {
        "service": service,
        "tags": f'{{"{tag_key}":"{tag_value}"}}',
        "limit": 100
    }
    response = requests.get(f"{JAEGER_URL}/api/traces", params=params)
    return response.json()["data"]
```

---

## Sampling Strategies / Стратегии сэмплирования

### Sampling Types / Типы сэмплирования

```
+------------------------------------------------------------------+
|                      SAMPLING STRATEGIES                          |
+------------------------------------------------------------------+
|                                                                   |
|  HEAD-BASED SAMPLING                                              |
|  (Decision at trace start)                                        |
|                                                                   |
|  Request --> [Sample?] --> Yes --> Trace all spans               |
|                  |                                                |
|                  +--> No --> Discard entire trace                |
|                                                                   |
|  Pros: Simple, low overhead                                       |
|  Cons: May miss important traces                                  |
|                                                                   |
+------------------------------------------------------------------+
|                                                                   |
|  TAIL-BASED SAMPLING                                              |
|  (Decision after trace complete)                                  |
|                                                                   |
|  Request --> Collect all spans --> [Analyze] --> Keep/Discard    |
|                                                                   |
|  Keep if:                                                         |
|    - Duration > threshold                                         |
|    - Contains errors                                              |
|    - Matches pattern                                              |
|                                                                   |
|  Pros: Captures interesting traces                                |
|  Cons: Higher resource usage, collector complexity                |
|                                                                   |
+------------------------------------------------------------------+
```

### Sampling Configuration / Конфигурация сэмплирования

```python
from opentelemetry.sdk.trace.sampling import (
    TraceIdRatioBased,
    ParentBased,
    ALWAYS_ON,
    ALWAYS_OFF
)

# Probabilistic sampling (10% of traces)
sampler = TraceIdRatioBased(0.1)

# Parent-based with different rates for root vs child
sampler = ParentBased(
    root=TraceIdRatioBased(0.1),  # 10% of root spans
    # Children inherit parent's sampling decision
)

# Rate limiting sampler (custom)
from opentelemetry.sdk.trace.sampling import Sampler, SamplingResult

class RateLimitingSampler(Sampler):
    def __init__(self, max_traces_per_second: float):
        self.max_traces = max_traces_per_second
        self.token_bucket = TokenBucket(max_traces_per_second)

    def should_sample(self, parent_context, trace_id, name, kind, attributes, links):
        if self.token_bucket.consume():
            return SamplingResult(
                decision=Decision.RECORD_AND_SAMPLE,
                attributes=attributes
            )
        return SamplingResult(decision=Decision.DROP)
```

### OTel Collector Tail Sampling / Tail-сэмплирование в коллекторе

```yaml
# otel-collector-config.yaml
processors:
  tail_sampling:
    decision_wait: 10s
    num_traces: 100000
    expected_new_traces_per_sec: 1000
    policies:
      # Always sample errors
      - name: errors-policy
        type: status_code
        status_code: {status_codes: [ERROR]}

      # Always sample slow traces (> 2s)
      - name: latency-policy
        type: latency
        latency: {threshold_ms: 2000}

      # Sample 10% of remaining traces
      - name: probabilistic-policy
        type: probabilistic
        probabilistic: {sampling_percentage: 10}

      # Always sample specific operations
      - name: critical-operations
        type: string_attribute
        string_attribute:
          key: operation.critical
          values: ["true"]
```

---

## Production Deployment / Развёртывание в продакшене

### High Availability Setup / Настройка высокой доступности

```yaml
# Kubernetes deployment example
apiVersion: apps/v1
kind: Deployment
metadata:
  name: otel-collector
spec:
  replicas: 3
  selector:
    matchLabels:
      app: otel-collector
  template:
    spec:
      containers:
        - name: otel-collector
          image: otel/opentelemetry-collector-contrib:latest
          resources:
            requests:
              memory: "512Mi"
              cpu: "500m"
            limits:
              memory: "2Gi"
              cpu: "2"
          ports:
            - containerPort: 4317  # OTLP gRPC
            - containerPort: 4318  # OTLP HTTP

---
apiVersion: v1
kind: Service
metadata:
  name: otel-collector
spec:
  type: ClusterIP
  ports:
    - name: otlp-grpc
      port: 4317
    - name: otlp-http
      port: 4318
  selector:
    app: otel-collector
```

### Collector Configuration / Конфигурация коллектора

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 10s
    send_batch_size: 1000

  memory_limiter:
    limit_mib: 1500
    spike_limit_mib: 500
    check_interval: 5s

  resource:
    attributes:
      - key: cluster
        value: production
        action: upsert

exporters:
  jaeger:
    endpoint: jaeger-collector:14250
    tls:
      insecure: true

  prometheus:
    endpoint: 0.0.0.0:8889

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch, resource]
      exporters: [jaeger]

    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [prometheus]
```

---

## Связано с

- [[Three-Pillars]]
- [[Prometheus-Grafana]]
- [[Log-Aggregation]]
- [[PV-Monitoring]]

## Ресурсы

1. OpenTelemetry Documentation: https://opentelemetry.io/docs/
2. Jaeger Documentation: https://www.jaegertracing.io/docs/
3. W3C Trace Context: https://www.w3.org/TR/trace-context/
4. "Distributed Tracing in Practice" by Austin Parker et al. (O'Reilly, 2020)
5. OpenTelemetry Python SDK: https://opentelemetry.io/docs/languages/python/
6. Sampling Best Practices: https://opentelemetry.io/docs/concepts/sampling/
7. OTel Collector Configuration: https://opentelemetry.io/docs/collector/configuration/
8. Google Dapper Paper: https://research.google/pubs/pub36356/

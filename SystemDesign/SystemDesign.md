---
tags:
  - system-design
  - moc
  - interview-prep
created: 2026-02-17
---

# System Design

## Что это

Карта знаний (Map of Content) по проектированию распределенных систем. Учебные материалы, паттерны, практические решения из проекта [[Polyvision]] и подготовка к system design интервью.

## Оркестрация

Управление сложными workflow, координация микросервисов, обработка ошибок.

- [[Orchestration-Patterns]] -- Saga, Choreography vs Orchestration, State Machine
- [[Celery-Patterns]] -- Task queue, retry, идемпотентность, dead letter
- [[Workflow-Engines]] -- Temporal, Airflow, Prefect, Celery сравнение
- [[Idempotency]] -- идемпотентные операции, idempotency keys
- [[PV-Orchestration]] -- Processing Orchestrator в Polyvision (state machine, HA через Redpanda)

## Брокеры сообщений

Event streaming, message queues, pub/sub паттерны.

- [[Message-Brokers-Overview]] -- Kafka, RabbitMQ, Redpanda, NATS сравнение
- [[Event-Streaming]] -- event sourcing, log compaction, replay
- [[Kafka-Internals]] -- партиции, consumer groups, exactly-once semantics
- [[Queue-vs-Stream]] -- когда queue (RabbitMQ), когда stream (Kafka/Redpanda)
- [[PV-Messaging]] -- Redpanda + dual Redis в Polyvision (ADR-009)

## Высокая доступность

Failover, leader election, replication, consensus.

- [[High-Availability]] -- SLO/SLA/SLI, nines of availability
- [[Leader-Election]] -- алгоритмы: Raft, Paxos, consumer groups
- [[Replication]] -- sync/async, multi-master, conflict resolution
- [[Circuit-Breaker]] -- паттерн Circuit Breaker, bulkhead, timeout
- [[Load-Balancing]] -- L4 vs L7, алгоритмы (round-robin, least-connections, consistent hashing)

## Хранение данных

Реляционные СУБД, аналитические хранилища, object storage, кеширование.

- [[Database-Design]] -- нормализация, индексы, партиционирование
- [[PostgreSQL-Patterns]] -- connection pooling (PgBouncer), JSONB, partitioning
- [[ClickHouse-Patterns]] -- columnar storage, MergeTree, materialized views
- [[Object-Storage]] -- S3 API, MinIO, Ceph, lifecycle policies
- [[Caching-Strategies]] -- cache-aside, write-through, TTL, eviction policies
- [[Redis-Patterns]] -- data structures, pub/sub, Lua scripting, eviction policies
- [[Time-Series-Data]] -- ClickHouse vs TimescaleDB vs InfluxDB
- [[PV-Data-Storage]] -- ClickHouse для детекций в Polyvision (ADR-021)

## Сети

API design, gateways, service mesh, протоколы.

- [[API-Design]] -- REST, gRPC, GraphQL, versioning
- [[API-Gateway]] -- паттерны: routing, auth, rate limiting, CORS
- [[Service-Mesh]] -- Istio, Linkerd, sidecar proxy
- [[DNS-and-Service-Discovery]] -- DNS, Consul, K8s services
- [[CDN]] -- content delivery, edge caching, signed URLs
- [[PV-Gateway]] -- Apache APISIX в Polyvision (ADR-023)

## Безопасность

Аутентификация, авторизация, шифрование, multi-tenancy.

- [[Authentication-Patterns]] -- JWT, OAuth2, session-based, API keys
- [[JWT-Deep-Dive]] -- RS256, EdDSA, claims, refresh tokens, revocation
- [[Authorization]] -- RBAC, ABAC, policy engines (OPA)
- [[Multi-Tenancy]] -- row-level isolation, schema-per-tenant, DB-per-tenant
- [[Cryptography-Basics]] -- symmetric/asymmetric, Ed25519, RSA, HMAC
- [[Secrets-Management]] -- Vault, Sealed Secrets, SOPS
- [[PV-Security]] -- Ed25519 device auth + RS256 user JWT в Polyvision (ADR-022)

## Наблюдаемость

Мониторинг, логирование, трейсинг, алертинг.

- [[Observability-Overview]] -- три столпа: metrics, logs, traces
- [[Prometheus-Grafana]] -- pull model, PromQL, дашборды
- [[Distributed-Tracing]] -- OpenTelemetry, Jaeger, trace context propagation
- [[Structured-Logging]] -- structlog, ELK, Loki
- [[SLO-SLI-SLA]] -- определение, расчет error budget

## Инфраструктура

Контейнеризация, оркестрация, CI/CD, IaC.

- [[Kubernetes-Architecture]] -- control plane, scheduling, networking
- [[Docker-Patterns]] -- multi-stage builds, layer caching, security
- [[K3s-Production]] -- lightweight K8s, embedded etcd, homelab
- [[CI-CD-Pipelines]] -- GitHub Actions, quality gates, deployment strategies
- [[Infrastructure-as-Code]] -- Terraform, Helm, Kustomize

## Справочные материалы

- [[Glossary-SystemDesign]] -- глоссарий терминов (EN/RU)
- [[Interview-Questions]] -- типовые вопросы system design интервью
- [[Estimation-Cheatsheet]] -- back-of-envelope calculations
- [[SystemDesign-Resources]] -- книги, курсы, статьи

## Polyvision как case study

Проект [[Polyvision]] используется как практический case study для изучения system design паттернов. Связанные заметки:

- [[PV-Orchestration]] -- workflow orchestration (Celery + state machine + Redpanda leader election)
- [[PV-Messaging]] -- event streaming (Redpanda) + task queue (Redis/Celery)
- [[PV-Data-Storage]] -- dual database (PostgreSQL + ClickHouse) + object storage (MinIO)
- [[PV-Gateway]] -- API Gateway (Apache APISIX с Python плагинами)
- [[PV-Security]] -- dual auth (RS256 users + Ed25519 devices) + multi-tenancy
- [[Polyvision-Stack]] -- полный список технологических решений с обоснованиями

## Связано с

- [[Polyvision]] -- проект спортивной аналитики
- [[Polyvision-Stack]] -- решения по стеку технологий
- [[Kubernetes]] -- оркестрация контейнеров
- [[Networking]] -- сети
- [[Homelab]] -- инфраструктура для staging

## Ресурсы

- "Designing Data-Intensive Applications" -- Martin Kleppmann
- "System Design Interview" -- Alex Xu (vol. 1 & 2)
- "Building Microservices" -- Sam Newman
- https://github.com/donnemartin/system-design-primer
- https://bytebytego.com/
- Polyvision docs: `~/Expirements/polyvision/docs/`

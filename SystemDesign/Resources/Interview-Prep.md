---
tags:
  - system-design
  - interview-prep
  - resources
created: 2026-02-17
---

# Подготовка к собеседованию по System Design / System Design Interview Preparation Guide

## Что это

Полное руководство по подготовке к собеседованиям по system design: структура интервью (45-60 минут), фреймворк RADIO (Requirements, Architecture, Data, Interfaces, Operations), 10 частых ошибок, советы по коммуникации, примеры вопросов по уровням (beginner/intermediate/advanced), пошаговый разбор URL Shortener, критерии оценки, советы на день собеседования и чеклисты.

---

## Interview Structure / Структура собеседования

### Standard Format (45-60 minutes)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SYSTEM DESIGN INTERVIEW                          │
├─────────────────────────────────────────────────────────────────────┤
│  0-5 min   │ Introduction & Problem Statement                      │
├─────────────────────────────────────────────────────────────────────┤
│  5-15 min  │ Requirements Clarification                            │
│            │ • Functional requirements                              │
│            │ • Non-functional requirements                          │
│            │ • Scale estimation (back-of-envelope)                  │
├─────────────────────────────────────────────────────────────────────┤
│  15-35 min │ High-Level Design                                     │
│            │ • System components                                    │
│            │ • Data flow                                           │
│            │ • API design                                          │
│            │ • Database schema                                     │
├─────────────────────────────────────────────────────────────────────┤
│  35-50 min │ Deep Dive                                             │
│            │ • Interviewer-directed exploration                    │
│            │ • Trade-off discussions                               │
│            │ • Scaling specific components                         │
├─────────────────────────────────────────────────────────────────────┤
│  50-60 min │ Wrap-up & Questions                                   │
│            │ • Summary of design                                   │
│            │ • Future improvements                                 │
│            │ • Your questions for interviewer                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Time Allocation Strategy

| Phase | Time | Your Goal |
|-------|------|-----------|
| Requirements | 10 min | Show you think before coding |
| High-Level Design | 20 min | Demonstrate architectural thinking |
| Deep Dive | 20 min | Show depth and trade-off analysis |
| Wrap-up | 5 min | Leave positive impression |

**Golden Rule:** Spend more time on requirements than you think you need. Rushing into design is the #1 mistake.

---

## The RADIO Framework / Фреймворк RADIO

A structured approach to tackling any system design problem.

### R - Requirements

**Goal:** Understand what to build before building it.

#### Functional Requirements

Ask: "What features must the system support?"

```
Questions to ask:
├── Who are the users? (consumers, businesses, internal)
├── What are the core use cases?
├── What are the input/output of the system?
├── What edge cases should we handle?
└── What can we explicitly NOT support (scope)?
```

**Example for URL Shortener:**
- Create short URL from long URL
- Redirect short URL to original
- Custom aliases (optional)?
- URL expiration?
- Analytics on clicks?

#### Non-Functional Requirements

Ask: "What qualities must the system have?"

```
Key NFRs to consider:
├── Scale: How many users? Requests per second?
├── Latency: What's acceptable response time?
├── Availability: What's the SLA? (99.9%? 99.99%?)
├── Consistency: Strong or eventual?
├── Durability: Can we lose data?
└── Security: Authentication, encryption, compliance?
```

#### Back-of-Envelope Calculations

**Traffic estimation:**
```
Example: URL Shortener

Daily active users: 100M
URLs shortened per user per day: 0.1
Total shortens per day: 10M
Shortens per second: 10M / 86400 ≈ 115 writes/sec

Read:Write ratio: 100:1
Reads per second: 115 × 100 = 11,500 reads/sec
```

**Storage estimation:**
```
URLs per day: 10M
URL size (long + short + metadata): 500 bytes
Storage per day: 10M × 500B = 5GB/day
Storage for 5 years: 5GB × 365 × 5 ≈ 9TB
```

**Memory for caching:**
```
Cache hot URLs (20% of traffic)
Daily unique URLs read: 100M
Cache 20%: 20M URLs
Size per URL: 500 bytes
Cache size: 20M × 500B = 10GB
```

---

### A - Architecture

**Goal:** Design the high-level system components and their interactions.

#### Start with a Simple Diagram

```
┌─────────┐     ┌──────────────┐     ┌─────────────┐
│ Clients │────▶│ Load Balancer│────▶│ Web Servers │
└─────────┘     └──────────────┘     └──────┬──────┘
                                            │
                       ┌────────────────────┼────────────────────┐
                       │                    │                    │
                       ▼                    ▼                    ▼
                 ┌──────────┐        ┌──────────┐         ┌──────────┐
                 │  Cache   │        │ Database │         │  Storage │
                 │ (Redis)  │        │(Postgres)│         │  (S3)    │
                 └──────────┘        └──────────┘         └──────────┘
```

#### Component Selection Rationale

Always explain WHY you choose each component:

| Component | Options | Selection Criteria |
|-----------|---------|-------------------|
| Load Balancer | Nginx, HAProxy, ALB | Traffic type, cost, features |
| Cache | Redis, Memcached | Data structures needed, persistence |
| Database | PostgreSQL, MongoDB, Cassandra | Data model, consistency needs |
| Queue | Kafka, RabbitMQ, SQS | Throughput, ordering, durability |
| Storage | S3, GCS, MinIO | Cost, access patterns, location |

---

### D - Data

**Goal:** Define data models, storage choices, and data flow.

#### Database Schema Design

```sql
-- Example: URL Shortener

-- Core table
CREATE TABLE urls (
    id BIGSERIAL PRIMARY KEY,
    short_code VARCHAR(10) UNIQUE NOT NULL,
    long_url TEXT NOT NULL,
    user_id BIGINT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    click_count BIGINT DEFAULT 0
);

-- Index for fast lookups
CREATE INDEX idx_short_code ON urls(short_code);
CREATE INDEX idx_user_urls ON urls(user_id, created_at DESC);
```

#### Database Selection

| Need | Choose | Why |
|------|--------|-----|
| Strong consistency, relations | PostgreSQL | ACID, mature |
| High write throughput | Cassandra | Distributed, tunable consistency |
| Flexible schema | MongoDB | Document model |
| Simple key-value | Redis | In-memory, fast |
| Time-series data | ClickHouse, TimescaleDB | Optimized for analytics |
| Search | Elasticsearch | Full-text, faceted |

#### Data Flow Diagrams

Show how data moves through the system:

```
Create Short URL:
Client → API Gateway → URL Service → Generate Short Code
                                   → Store in Database
                                   → Invalidate Cache
                                   → Return Short URL

Redirect:
Client → CDN (cache hit?) → Load Balancer → URL Service
                                          → Check Cache
                                          → Query Database
                                          → Increment Analytics
                                          → Return 301 Redirect
```

---

### I - Interfaces

**Goal:** Define APIs and contracts between components.

#### API Design

```
REST API Example:

POST /api/v1/urls
Request:
{
    "long_url": "https://example.com/very/long/path",
    "custom_alias": "my-link",  // optional
    "expires_in": 86400         // optional, seconds
}

Response:
{
    "short_url": "https://short.ly/abc123",
    "short_code": "abc123",
    "created_at": "2026-01-12T10:00:00Z",
    "expires_at": "2026-01-13T10:00:00Z"
}

GET /{short_code}
Response: 301 Redirect to long_url

GET /api/v1/urls/{short_code}/stats
Response:
{
    "short_code": "abc123",
    "click_count": 1523,
    "unique_visitors": 892,
    "top_referrers": [...]
}
```

#### API Best Practices

- **Versioning**: `/api/v1/` prefix
- **Pagination**: `?page=1&limit=20` or cursor-based
- **Filtering**: `?status=active&created_after=2026-01-01`
- **Rate limiting**: `X-RateLimit-Remaining` headers
- **Error format**: Consistent error response structure

---

### O - Operations

**Goal:** Address reliability, monitoring, and operational concerns.

#### Scalability

```
Horizontal Scaling:

                    ┌─────────────┐
                    │Load Balancer│
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           │               │               │
      ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
      │Server 1 │    │Server 2 │    │Server 3 │
      └────┬────┘    └────┬────┘    └────┬────┘
           │               │               │
           └───────────────┼───────────────┘
                    ┌──────▼──────┐
                    │   Database  │
                    │   Cluster   │
                    └─────────────┘
```

#### Reliability Patterns

| Pattern | Problem Solved | Implementation |
|---------|---------------|----------------|
| Circuit Breaker | Cascading failures | Hystrix, Resilience4j |
| Retry with Backoff | Transient failures | Exponential backoff |
| Bulkhead | Resource isolation | Thread pools, containers |
| Rate Limiting | Overload protection | Token bucket, sliding window |
| Health Checks | Failure detection | /health endpoints |

#### Monitoring

**Four Golden Signals:**
1. **Latency**: Response time (p50, p99, p999)
2. **Traffic**: Requests per second
3. **Errors**: Error rate, error types
4. **Saturation**: CPU, memory, queue depth

```
Alerting Rules Example:
├── Error rate > 1% for 5 minutes → Page on-call
├── p99 latency > 500ms for 5 minutes → Alert
├── CPU > 80% for 10 minutes → Scale out
└── Database connections > 80% → Alert
```

---

## Common Mistakes / Частые ошибки

### Mistake 1: Jumping to Solutions

**Wrong:** "Let's use Kafka for messaging."
**Right:** "What are our messaging requirements? Do we need ordering? What throughput?"

**Fix:** Always spend 5-10 minutes on requirements before drawing anything.

---

### Mistake 2: Not Driving the Conversation

**Wrong:** Waiting for interviewer to ask questions.
**Right:** "I'll start with requirements, then move to high-level design. Does that work?"

**Fix:** Take ownership. Treat it as a collaborative design session, not an interrogation.

---

### Mistake 3: Over-Engineering

**Wrong:** "We need Kafka, Redis, Elasticsearch, MongoDB, and Kubernetes from day one."
**Right:** Start simple, scale based on requirements.

**Fix:** Ask about scale first. Design for the stated requirements, mention future scaling.

---

### Mistake 4: Under-Engineering

**Wrong:** "Single server with SQLite should work."
**Right:** Design for the scale mentioned in requirements.

**Fix:** Do back-of-envelope math. If the math says you need distribution, design for it.

---

### Mistake 5: Ignoring Trade-offs

**Wrong:** "MongoDB is the best database."
**Right:** "MongoDB works well here because we need flexible schema, but we trade strong consistency."

**Fix:** Every choice has trade-offs. Articulate them clearly.

---

### Mistake 6: Not Asking Clarifying Questions

**Wrong:** Assuming you understand the problem.
**Right:** "When you say 'real-time', do you mean sub-100ms or eventual within seconds?"

**Fix:** Prepare a mental checklist of clarifying questions.

---

### Mistake 7: Tunnel Vision

**Wrong:** Spending 30 minutes perfecting the database schema.
**Right:** Cover the entire system, then deep-dive where interviewer wants.

**Fix:** Time-box each section. Check in with interviewer regularly.

---

### Mistake 8: Not Drawing Diagrams

**Wrong:** Describing architecture only verbally.
**Right:** Drawing clear, labeled diagrams.

**Fix:** Practice drawing quickly. Use consistent symbols.

---

### Mistake 9: Forgetting About Failure Modes

**Wrong:** Designing only the happy path.
**Right:** "What happens if the cache goes down? The database fails?"

**Fix:** Explicitly discuss failure scenarios for critical components.

---

### Mistake 10: Not Handling Edge Cases

**Wrong:** Ignoring race conditions, duplicate requests.
**Right:** "For idempotency, we'll use request IDs..."

**Fix:** Think about: duplicates, race conditions, clock skew, partial failures.

---

## Communication Tips / Советы по коммуникации

### Structure Your Thoughts

```
Pattern: "I'm going to discuss X, then Y, then Z."

Example:
"Let me start by clarifying requirements, then I'll sketch the
high-level architecture, and we can deep-dive into any area
you'd like. Sound good?"
```

### Think Aloud

```
Pattern: "I'm considering A vs B because..."

Example:
"I'm thinking about whether to use SQL or NoSQL here. Given our
read-heavy workload and need for flexible queries, SQL with read
replicas seems better than Cassandra. What do you think?"
```

### Summarize Periodically

```
Pattern: "So far we have..."

Example:
"Let me summarize: we have a load balancer in front of stateless
API servers, Redis for caching hot data, and PostgreSQL with read
replicas for persistent storage. Now let's discuss the message queue."
```

### Ask for Feedback

```
Pattern: "Does this make sense? Any concerns?"

Example:
"I've designed the basic read path. Before moving to writes,
does the read path make sense? Anything you'd like to explore
more deeply?"
```

### Acknowledge Trade-offs

```
Pattern: "We gain X but we trade Y."

Example:
"By choosing eventual consistency, we gain higher availability
and lower latency, but we need to handle the case where a user
might not see their write immediately."
```

### Use Precise Language

| Avoid | Use Instead |
|-------|-------------|
| "It's fast" | "p99 latency under 50ms" |
| "It's scalable" | "Horizontally scalable to 10K RPS" |
| "Lots of data" | "~500GB with 10% monthly growth" |
| "Highly available" | "99.9% uptime, 8.7 hours downtime/year" |

---

## Sample Questions / Примеры вопросов

### Beginner Level

| Question | Key Focus Areas |
|----------|-----------------|
| Design URL Shortener | Hashing, database choice, caching |
| Design Pastebin | Storage, expiration, rate limiting |
| Design Rate Limiter | Algorithms (token bucket, sliding window) |
| Design Key-Value Store | Partitioning, replication |

### Intermediate Level

| Question | Key Focus Areas |
|----------|-----------------|
| Design Twitter | Fan-out, timeline generation, caching |
| Design Instagram | Image storage, CDN, news feed |
| Design Web Crawler | Distributed crawling, politeness, dedup |
| Design Notification System | Push/pull, multiple channels, delivery guarantees |

### Advanced Level

| Question | Key Focus Areas |
|----------|-----------------|
| Design Google Maps | Graph algorithms, real-time updates, tile serving |
| Design Uber | Real-time location, matching, surge pricing |
| Design YouTube | Video processing, recommendation, CDN |
| Design Distributed Database | Consensus, replication, sharding |

---

### Sample Walkthrough: Design URL Shortener

#### Requirements (5 min)

**Functional:**
- Shorten long URLs to 7-character codes
- Redirect short URLs to original
- Optional custom aliases
- URL expiration (optional)
- Analytics (optional, not in v1)

**Non-functional:**
- 100M DAU
- 10M new URLs/day (115/sec writes)
- 100:1 read:write ratio (11,500/sec reads)
- Low latency (<100ms p99)
- High availability (99.9%)
- URLs never expire by default

**Storage:**
- 5 years retention: ~9TB
- Cache for hot URLs: ~10GB

#### High-Level Design (15 min)

```
                           ┌──────────────┐
                           │   Client     │
                           └──────┬───────┘
                                  │
                           ┌──────▼───────┐
                           │     CDN      │ ◄── Static assets + cache
                           └──────┬───────┘
                                  │
                           ┌──────▼───────┐
                           │ API Gateway  │ ◄── Rate limiting, auth
                           └──────┬───────┘
                                  │
               ┌──────────────────┼──────────────────┐
               │                  │                  │
        ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐
        │ URL Service │    │ URL Service │    │ URL Service │
        │  Instance   │    │  Instance   │    │  Instance   │
        └──────┬──────┘    └──────┬──────┘    └──────┬──────┘
               │                  │                  │
               └──────────────────┼──────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
             ┌──────▼──────┐  ┌───▼────┐  ┌─────▼─────┐
             │   Redis     │  │ Counter│  │  Primary  │
             │   Cache     │  │ Service│  │PostgreSQL │
             └─────────────┘  └────────┘  └─────┬─────┘
                                                │
                                          ┌─────▼─────┐
                                          │  Replica  │
                                          │PostgreSQL │
                                          └───────────┘
```

#### Data Model (5 min)

```sql
CREATE TABLE urls (
    id BIGSERIAL PRIMARY KEY,
    short_code VARCHAR(10) UNIQUE NOT NULL,
    long_url TEXT NOT NULL,
    user_id BIGINT,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);

CREATE INDEX idx_short_code ON urls(short_code);
```

#### Short Code Generation

Option 1: Base62 encoding of counter
- Counter service provides unique IDs
- Encode to base62: `[a-zA-Z0-9]`
- 7 characters = 62^7 = 3.5 trillion combinations

Option 2: Random generation with collision check
- Generate random 7-char string
- Check database for collision
- Retry if collision (low probability)

**Choice:** Base62 counter for predictability and no collision checks.

#### Deep Dive: Scaling (10 min)

**Caching Strategy:**
- Cache-aside pattern
- Redis cluster with 10GB capacity
- TTL: 24 hours for hot URLs
- Cache hit ratio target: 80%+

**Database Scaling:**
- Read replicas for redirect lookups
- Primary for writes (115/sec is manageable)
- Partition by short_code if needed later

**Availability:**
- Multi-AZ deployment
- Health checks on all services
- Graceful degradation: serve from cache if DB down

---

## Evaluation Criteria / Критерии оценки

### What Interviewers Look For

| Criterion | Weight | What They Observe |
|-----------|--------|------------------|
| Problem Exploration | 20% | Asking good questions, defining scope |
| High-Level Design | 25% | Logical component selection, data flow |
| Technical Depth | 25% | Understanding of trade-offs, algorithms |
| Communication | 15% | Clarity, structure, collaboration |
| Prioritization | 15% | Focusing on important aspects |

### Scoring Rubric

**Strong Hire:**
- Clarifies requirements thoroughly
- Designs appropriate system for scale
- Articulates trade-offs clearly
- Handles deep-dive questions well
- Communicates proactively

**Hire:**
- Covers most requirements
- Reasonable design decisions
- Some trade-off discussion
- Handles basic deep-dives
- Communicates adequately

**No Hire:**
- Jumps to solution without requirements
- Design doesn't meet scale requirements
- Cannot explain decisions
- Struggles with follow-up questions
- Poor communication

---

## Day-of Tips / Советы на день собеседования

### Before the Interview

1. **Sleep well** - Cognitive function degrades with fatigue
2. **Review your notes** - Quick refresh of key patterns
3. **Prepare examples** - From your own experience
4. **Test your setup** - Video, audio, drawing tools (if remote)
5. **Have water nearby** - 45-60 minutes is a long time to talk

### During the Interview

1. **Breathe** - Pause before answering complex questions
2. **Write down requirements** - Reference them throughout
3. **Check in** - "Does this approach make sense?"
4. **Manage time** - Don't spend 30 min on one component
5. **Stay calm on mistakes** - Course-correct gracefully

### Drawing Tips (Whiteboard/Virtual)

1. **Start center-left** - Leave room to expand right
2. **Use consistent symbols** - Boxes for services, cylinders for DBs
3. **Label everything** - Don't assume interviewer can read your mind
4. **Draw arrows for data flow** - Direction matters
5. **Color-code if possible** - Read path vs write path

### Virtual Interview Specific

1. **Practice with the tool** - Excalidraw, Miro, whatever they use
2. **Share screen early** - Catch technical issues
3. **Speak while drawing** - Silence can feel awkward
4. **Check audio regularly** - "Can you still hear me?"

---

## Quick Reference Card / Быстрая справка

### Clarification Questions Checklist

```
□ Who are the users?
□ What are the core features?
□ What's the expected scale (DAU, QPS)?
□ What's the read:write ratio?
□ What latency is acceptable?
□ What's the availability requirement?
□ Strong or eventual consistency?
□ What's the data retention period?
□ Any compliance requirements?
□ What can we explicitly NOT support?
```

### Components Cheat Sheet

```
Frontend:
├── CDN → Static assets, edge caching
├── Load Balancer → Traffic distribution
└── API Gateway → Auth, rate limiting, routing

Compute:
├── Stateless Services → Horizontal scaling
├── Workers → Async processing
└── Schedulers → Cron jobs, delayed tasks

Storage:
├── SQL (PostgreSQL) → Relations, ACID
├── NoSQL (MongoDB) → Flexible schema
├── Wide-column (Cassandra) → Write-heavy
├── Cache (Redis) → Hot data, sessions
├── Object (S3) → Files, media
└── Search (Elasticsearch) → Full-text

Messaging:
├── Kafka → Event streaming, high throughput
├── RabbitMQ → Task queues, routing
└── SQS → Simple queuing

Coordination:
├── ZooKeeper → Distributed coordination
├── etcd → Configuration, service discovery
└── Consul → Service mesh, health checks
```

### Time Management

```
0:00  - Start, introductions
0:05  - Requirements (10 min) ← Don't rush!
0:15  - High-level design (15-20 min)
0:35  - Deep dive (15-20 min)
0:50  - Wrap-up, questions (5-10 min)
0:60  - End
```

---

## Final Advice / Заключительный совет

1. **Practice regularly** - Do 2-3 mock interviews per week leading up to real ones
2. **Study real systems** - Read engineering blogs from major tech companies
3. **Build projects** - Nothing beats hands-on experience
4. **Learn from feedback** - Every interview is a learning opportunity
5. **Stay curious** - System design is about continuous learning

**Remember:** The goal isn't to give a "correct" answer (there isn't one). It's to demonstrate how you think through complex problems collaboratively.

---

## Связано с

- [[Glossary-SystemDesign]]
- [[Resources/Books]]
- [[Resources/Courses]]

## Ресурсы

1. System Design Primer: https://github.com/donnemartin/system-design-primer
2. Grokking the System Design Interview: https://www.educative.io/courses/grokking-the-system-design-interview
3. ByteByteGo: https://bytebytego.com
4. Pramp (Free Mock Interviews): https://www.pramp.com
5. Excalidraw (Drawing Tool): https://excalidraw.com

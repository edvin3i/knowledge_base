---
tags:
  - system-design
  - orchestration
  - workflow
created: 2026-02-17
---

# Обзор оркестрации рабочих процессов

## Что это
Workflow orchestration -- автоматизированная координация и управление сложными многошаговыми процессами в распределённых системах. Два основных подхода: task-centric (DAG, Airflow) и data-centric (Event Sourcing, Temporal).

## What is Workflow Orchestration? / Что такое оркестрация?

**Workflow orchestration** is the automated coordination and management of complex, multi-step processes across distributed systems.

**Оркестрация рабочих процессов** -- это автоматизированная координация и управление сложными многошаговыми процессами в распределённых системах.

### Core Problem / Основная проблема

Without orchestration, managing distributed workflows is error-prone:

```
┌─────────────────────────────────────────────────────────────────────┐
│  WITHOUT ORCHESTRATION                                               │
│                                                                      │
│  Service A → Service B → Service C → Service D                      │
│       ↓           ↓           ↓           ↓                         │
│   What if B     What if C    How to     Who tracks                  │
│   fails?        times out?   retry?     progress?                   │
│                                                                      │
│  Problems:                                                           │
│  • No central state management                                       │
│  • Retry logic scattered across services                            │
│  • Hard to debug failures                                           │
│  • No visibility into workflow progress                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Two Paradigms / Две парадигмы

### 1. Task-Centric Orchestration / Оркестрация, ориентированная на задачи

**Definition:** Workflows organized as DAGs (Directed Acyclic Graphs) of tasks. Scheduler determines execution order based on dependencies.

**Определение:** Рабочие процессы организованы как DAG (Направленные ациклические графы) задач. Планировщик определяет порядок выполнения на основе зависимостей.

**Examples / Примеры:** Apache [[Airflow]], Luigi, Prefect

```
┌─────────────────────────────────────────────────────────────────────┐
│  TASK-CENTRIC (DAG-based)                                           │
│                                                                      │
│        ┌─────────┐                                                  │
│        │ Extract │                                                  │
│        └────┬────┘                                                  │
│             │                                                        │
│     ┌───────┴───────┐                                               │
│     ▼               ▼                                               │
│  ┌──────┐       ┌──────┐                                            │
│  │Trans │       │Trans │                                            │
│  │form A│       │form B│                                            │
│  └───┬──┘       └──┬───┘                                            │
│      │             │                                                 │
│      └──────┬──────┘                                                │
│             ▼                                                        │
│        ┌─────────┐                                                  │
│        │  Load   │                                                  │
│        └─────────┘                                                  │
│                                                                      │
│  Characteristics:                                                    │
│  • Static DAG defined at design time                                │
│  • Scheduled execution (cron-like)                                  │
│  • Good for ETL pipelines                                           │
│  • Batch-oriented                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

**Best for / Лучше всего для:**
- ETL (Extract-Transform-Load) / Data pipelines / Пайплайны данных
- Batch processing / Пакетная обработка
- Scheduled jobs / Запланированные задачи
- ML (Machine Learning) training pipelines / Пайплайны обучения моделей

---

### 2. Data-Centric / Event-Driven Orchestration

**Definition:** Workflows as stateful, durable functions that react to events. State is automatically persisted and recovered.

**Определение:** Рабочие процессы как состояние-ориентированные, устойчивые функции, реагирующие на события. Состояние автоматически сохраняется и восстанавливается.

**Examples / Примеры:** [[Temporal]], Cadence, Azure Durable Functions

```
┌─────────────────────────────────────────────────────────────────────┐
│  DATA-CENTRIC (Event Sourcing)                                      │
│                                                                      │
│  Workflow Code (looks like normal code):                            │
│  ┌───────────────────────────────────────┐                          │
│  │ async def process_order(order_id):    │                          │
│  │     payment = await charge_card()     │  ← Activity call        │
│  │     if payment.failed:                │                          │
│  │         await refund()                │  ← Branching             │
│  │         return                        │                          │
│  │     await ship_order()                │  ← Activity call        │
│  │     await workflow.sleep(days=7)      │  ← Durable timer        │
│  │     await send_review_request()       │                          │
│  └───────────────────────────────────────┘                          │
│                                                                      │
│  Under the hood (Event History):                                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Event 1: WorkflowStarted                                     │   │
│  │ Event 2: ActivityScheduled(charge_card)                      │   │
│  │ Event 3: ActivityCompleted(charge_card, result=success)      │   │
│  │ Event 4: ActivityScheduled(ship_order)                       │   │
│  │ Event 5: ActivityCompleted(ship_order, result=success)       │   │
│  │ Event 6: TimerStarted(7 days)                                │   │
│  │ Event 7: TimerFired                                          │   │
│  │ Event 8: ActivityScheduled(send_review_request)              │   │
│  │ ...                                                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  On crash: Replay events → Reconstruct state                        │
└─────────────────────────────────────────────────────────────────────┘
```

**Best for / Лучше всего для:**
- Microservices orchestration / Оркестрация микросервисов
- Long-running processes (hours, days, weeks) / Долгие процессы
- Event-driven workflows / Событийно-управляемые процессы
- Business transactions / Бизнес-транзакции

---

## Comparison Table / Сравнительная таблица

| Aspect | Task-Centric ([[Airflow]]) | Data-Centric ([[Temporal]]) |
|--------|------------------------|-------------------------|
| **Primary unit** / Основная единица | Task / Задача | Activity / Активность |
| **Workflow definition** / Определение workflow | Static DAG / Статический DAG | Code (any language) / Код |
| **Execution model** / Модель выполнения | Scheduled / По расписанию | Event-driven / По событиям |
| **State management** / Управление состоянием | External (DB) / Внешнее | Built-in (Event Sourcing) / Встроенное |
| **Failure handling** / Обработка ошибок | Task-level retry / Повтор на уровне задачи | Automatic replay / Автоматический реплей |
| **Scalability pattern** / Паттерн масштабирования | Multiple schedulers / Несколько планировщиков | History Shards / Шарды истории |
| **Best for** / Лучше для | Data pipelines / Пайплайны данных | Business workflows / Бизнес-процессы |
| **Learning curve** / Кривая обучения | Lower / Ниже | Higher / Выше |

---

## Orchestration vs Choreography / Оркестрация vs Хореография

Two approaches to coordinate distributed transactions (Sagas):

Два подхода к координации распределённых транзакций (Саги):

### Choreography (Decentralized) / Хореография (Децентрализованная)

```
┌─────────────────────────────────────────────────────────────────────┐
│  CHOREOGRAPHY                                                        │
│                                                                      │
│  No central coordinator. Services react to events.                  │
│  Нет центрального координатора. Сервисы реагируют на события.       │
│                                                                      │
│  ┌─────────┐    event     ┌─────────┐    event     ┌─────────┐     │
│  │ Order   │───────────→  │ Payment │───────────→  │Inventory│     │
│  │ Service │              │ Service │              │ Service │     │
│  └─────────┘              └─────────┘              └─────────┘     │
│       ↑                        │                        │           │
│       └────────────────────────┴────────────────────────┘           │
│                    compensating events                              │
│                                                                      │
│  Pros:                          Cons:                               │
│  • Loose coupling               • Hard to track overall flow        │
│  • Services independent         • Cyclic dependencies possible      │
│  • Simpler services             • No central visibility             │
└─────────────────────────────────────────────────────────────────────┘
```

### Orchestration (Centralized) / Оркестрация (Централизованная)

```
┌─────────────────────────────────────────────────────────────────────┐
│  ORCHESTRATION                                                       │
│                                                                      │
│  Central coordinator manages the flow.                              │
│  Центральный координатор управляет потоком.                         │
│                                                                      │
│                    ┌─────────────────┐                              │
│                    │   Orchestrator   │                              │
│                    │  (Saga Manager)  │                              │
│                    └────────┬────────┘                              │
│                             │                                        │
│         ┌───────────────────┼───────────────────┐                   │
│         ▼                   ▼                   ▼                   │
│  ┌─────────┐         ┌─────────┐         ┌─────────┐               │
│  │ Order   │         │ Payment │         │Inventory│               │
│  │ Service │         │ Service │         │ Service │               │
│  └─────────┘         └─────────┘         └─────────┘               │
│                                                                      │
│  Pros:                          Cons:                               │
│  • Clear flow visibility        • Orchestrator is SPOF             │
│  • Easier debugging             • Services coupled to orchestrator  │
│  • Central state management     • Additional infrastructure         │
└─────────────────────────────────────────────────────────────────────┘
```

### When to Use / Когда использовать

| Scenario | Choreography | Orchestration |
|----------|--------------|---------------|
| Few services (2-3) | Prefer | Overkill |
| Many services (5+) | Avoid | Prefer |
| Complex business logic | Hard | Easy |
| Team independence | Better | Worse |
| Debugging needs | Harder | Easier |
| Existing event bus | Good fit | May need new infra |

---

## Key Industry Players / Ключевые игроки

### 1. Apache [[Airflow]]

**Origin:** Airbnb (2014), open-sourced 2015
**Type:** Task-centric, DAG-based scheduler
**Use case:** ETL, ML pipelines, batch jobs

**Evolution:**
- Airflow 1.x: Single scheduler (SPOF)
- Airflow 2.x: Multiple schedulers with DB-based coordination

### 2. [[Temporal]]

**Origin:** Fork of Uber Cadence (2019)
**Type:** Data-centric, durable execution
**Use case:** Microservices, business workflows, long-running processes

**Key features:**
- History Shards for scalability
- Multi-language SDKs (Go, Java, Python, TypeScript)
- Temporal Cloud (managed) + Self-hosted

### 3. [[Conductor]]

**Origin:** Netflix (2016)
**Type:** JSON-defined workflows, visual debugging
**Use case:** Microservice orchestration, media processing

**Key features:**
- JSON workflow definition
- Web UI for visualization
- Lightweight footprint

### 4. Uber Cadence

**Origin:** Uber (2017)
**Type:** Data-centric ([[Temporal]]'s predecessor)
**Use case:** Same as [[Temporal]]

**Note:** Development has slowed since [[Temporal]] fork. Consider [[Temporal]] for new projects.

---

## Decision Framework / Фреймворк принятия решений

```
┌─────────────────────────────────────────────────────────────────────┐
│  CHOOSING AN ORCHESTRATION APPROACH                                  │
│                                                                      │
│  Q1: What's your primary workload?                                  │
│  ├── ETL/Batch data pipelines → Consider Airflow                    │
│  ├── Microservice coordination → Consider Temporal/Conductor        │
│  └── Simple 2-3 service flows → Consider choreography               │
│                                                                      │
│  Q2: How important is durability?                                   │
│  ├── Workflows can restart from beginning → Simpler solution OK     │
│  └── Must resume from exact point → Need Temporal-style             │
│                                                                      │
│  Q3: Workflow duration?                                             │
│  ├── Minutes → Any solution works                                   │
│  ├── Hours/Days → Need durable execution                            │
│  └── Weeks/Months → Temporal is ideal                               │
│                                                                      │
│  Q4: Team expertise?                                                │
│  ├── Python + SQL focused → Airflow is familiar                     │
│  ├── Go/Java microservices → Temporal fits well                     │
│  └── Want JSON-based → Conductor is accessible                      │
│                                                                      │
│  Q5: Operational complexity tolerance?                              │
│  ├── Managed preferred → Temporal Cloud, MWAA (AWS Airflow)        │
│  └── Self-hosted OK → Any solution                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Interview Questions Preview / Превью вопросов для интервью

1. **What's the difference between orchestration and choreography?**
   Какая разница между оркестрацией и хореографией?

2. **When would you choose [[Airflow]] over [[Temporal]]?**
   Когда бы вы выбрали [[Airflow]] вместо [[Temporal]]?

3. **How does event sourcing help with workflow durability?**
   Как [[Event-Sourcing]] помогает с устойчивостью workflow?

4. **What is a History Shard in [[Temporal]]?**
   Что такое History Shard в [[Temporal]]?

Full questions with answers: [[Interview-Orchestration]]

## Связано с
- [[Temporal]]
- [[Conductor]]
- [[Airflow]]
- [[PV-Orchestration]]

## Ресурсы
- [Temporal Documentation](https://docs.temporal.io)
- [Apache Airflow Documentation](https://airflow.apache.org/docs/)
- [Netflix Conductor](https://netflix.github.io/conductor/)
- [State of Workflow Orchestration 2025](https://www.pracdata.io/p/state-of-workflow-orchestration-ecosystem-2025)
- [Comparing Orchestration Frameworks](https://medium.com/@natesh.somanna/comparing-orchestration-frameworks)

---
tags:
  - system-design
  - orchestration
  - airflow
created: 2026-02-17
---

# Архитектура Apache Airflow

## Что это
Apache Airflow -- платформа с открытым исходным кодом для программного создания, планирования и мониторинга рабочих процессов. Разработана в Airbnb (2014), передана Apache (2016). Основана на DAG (Directed Acyclic Graph) -- направленных ациклических графах задач.

## What is Apache Airflow? / Что такое Apache Airflow?

**Apache Airflow** is an open-source platform for programmatically authoring, scheduling, and monitoring workflows. Developed at Airbnb (2014), donated to Apache (2016).

**Apache Airflow** -- это платформа с открытым исходным кодом для программного создания, планирования и мониторинга рабочих процессов. Разработана в Airbnb (2014), передана Apache (2016).

### Core Concept: DAGs / Основная концепция: DAG

**DAG (Directed Acyclic Graph)** -- Направленный ациклический граф

```
┌─────────────────────────────────────────────────────────────────────┐
│  AIRFLOW DAG CONCEPT                                                │
│                                                                      │
│  DAG = Collection of tasks with dependencies                        │
│  DAG = Коллекция задач с зависимостями                             │
│                                                                      │
│           ┌─────────┐                                               │
│           │ Extract │                                               │
│           └────┬────┘                                               │
│                │                                                     │
│        ┌───────┴───────┐                                            │
│        ▼               ▼                                            │
│   ┌─────────┐    ┌─────────┐                                       │
│   │Transform│    │Transform│                                       │
│   │  Users  │    │ Events  │                                       │
│   └────┬────┘    └────┬────┘                                       │
│        │              │                                             │
│        └───────┬──────┘                                             │
│                ▼                                                     │
│           ┌─────────┐                                               │
│           │  Load   │                                               │
│           └────┬────┘                                               │
│                ▼                                                     │
│           ┌─────────┐                                               │
│           │ Notify  │                                               │
│           └─────────┘                                               │
│                                                                      │
│  Properties:                                                        │
│  • Directed: Tasks have upstream/downstream relationships          │
│  • Acyclic: No circular dependencies (A→B→C→A is invalid)         │
│  • Graph: Multiple paths, branches, joins are allowed              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Architecture Overview / Обзор архитектуры

### Airflow 2.x Architecture / Архитектура Airflow 2.x

```
┌─────────────────────────────────────────────────────────────────────┐
│                      AIRFLOW 2.x ARCHITECTURE                       │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                        WEB SERVER                            │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │   │
│  │  │   Flask UI   │  │   REST API   │  │   Auth/RBAC  │      │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      SCHEDULER(S)                            │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │   │
│  │  │ DAG Parser   │  │ Task Queue   │  │   Executor   │      │   │
│  │  │ (File Proc.) │  │ Manager      │  │   Interface  │      │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘      │   │
│  │         │                 │                 │               │   │
│  │  ┌──────┴─────────────────┴─────────────────┴──────┐       │   │
│  │  │              METADATA DATABASE                   │       │   │
│  │  │           (PostgreSQL / MySQL)                   │       │   │
│  │  └─────────────────────────────────────────────────┘       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                        WORKERS                               │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐            │   │
│  │  │  Worker 1  │  │  Worker 2  │  │  Worker N  │            │   │
│  │  │ (Celery/K8s│  │ (Celery/K8s│  │ (Celery/K8s│            │   │
│  │  │ /Local)    │  │ /Local)    │  │ /Local)    │            │   │
│  │  └────────────┘  └────────────┘  └────────────┘            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      DAG FILES                               │   │
│  │  /dags/etl_pipeline.py                                      │   │
│  │  /dags/ml_training.py                                       │   │
│  │  /dags/reporting.py                                         │   │
│  │  (Shared filesystem or Git-sync)                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Breakdown / Разбор компонентов

| Component | Role (EN) | Роль (RU) |
|-----------|-----------|-----------|
| **Web Server** | UI + REST API for monitoring | UI + REST API для мониторинга |
| **Scheduler** | Parses DAGs, schedules tasks | Парсит DAG, планирует задачи |
| **Executor** | Runs tasks (Celery/K8s/Local) | Запускает задачи |
| **Worker** | Executes individual tasks | Выполняет отдельные задачи |
| **Metadata DB** | Stores DAG runs, task states | Хранит запуски DAG, состояния |
| **DAG Files** | Python files defining workflows | Python-файлы с workflow |

---

## Evolution: Airflow 1.x -> 2.x / Эволюция: Airflow 1.x -> 2.x

### Airflow 1.x Problems / Проблемы Airflow 1.x

```
┌─────────────────────────────────────────────────────────────────────┐
│  AIRFLOW 1.x LIMITATIONS                                            │
│                                                                      │
│  1. SINGLE SCHEDULER (SPOF)                                         │
│     ┌──────────────┐                                               │
│     │  Scheduler   │ ← Single point of failure                     │
│     └──────┬───────┘   No HA without external tooling              │
│            │                                                        │
│                                                                      │
│  2. DATABASE BOTTLENECK                                             │
│     All scheduler decisions go through single DB                    │
│     Lock contention on task_instance table                         │
│     ~100 task instances/second limit                               │
│                                                                      │
│  3. SLOW DAG PARSING                                                │
│     Scheduler re-parses all DAG files every loop                   │
│     1000+ DAGs = minutes of parsing overhead                       │
│                                                                      │
│  4. NO TASK-LEVEL SCALING                                           │
│     All tasks in same executor pool                                │
│     No resource isolation between DAGs                             │
└─────────────────────────────────────────────────────────────────────┘
```

### Airflow 2.x Improvements / Улучшения Airflow 2.x

```
┌─────────────────────────────────────────────────────────────────────┐
│  AIRFLOW 2.x IMPROVEMENTS                                           │
│                                                                      │
│  1. MULTIPLE SCHEDULERS (HA)                                        │
│     ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│     │ Scheduler 1 │  │ Scheduler 2 │  │ Scheduler 3 │             │
│     └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│            │                │                │                      │
│            └────────────────┼────────────────┘                      │
│                             ▼                                       │
│                    ┌─────────────────┐                             │
│                    │  Database with  │                             │
│                    │  Row-level      │                             │
│                    │  Locking        │                             │
│                    └─────────────────┘                             │
│                                                                      │
│  2. FAST DAG PROCESSOR                                              │
│     • Separate DAG processor component                             │
│     • Only re-parses changed files                                 │
│     • Serialized DAGs stored in DB                                 │
│     • Scheduler reads from DB, not files                           │
│                                                                      │
│  3. TASK INSTANCE SCHEDULING IMPROVEMENTS                           │
│     • Batch operations                                              │
│     • Optimized queries                                             │
│     • ~10x throughput improvement                                   │
│                                                                      │
│  4. TASKFLOW API (Python decorators)                                │
│     @task                                                           │
│     def extract(): ...                                              │
│     @task                                                           │
│     def transform(data): ...                                        │
│                                                                      │
│     extract() >> transform()  # Automatic XCom                     │
└─────────────────────────────────────────────────────────────────────┘
```

### HA Scheduler Deep Dive / Глубокое погружение в HA Scheduler

```
┌─────────────────────────────────────────────────────────────────────┐
│  AIRFLOW 2.x SCHEDULER HA MECHANISM                                 │
│                                                                      │
│  Problem: Multiple schedulers must not schedule same task twice     │
│  Solution: Database row-level locking with "SELECT FOR UPDATE"      │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  SCHEDULING LOOP (each scheduler)                            │   │
│  │                                                               │   │
│  │  1. SELECT * FROM task_instance                              │   │
│  │     WHERE state = 'queued'                                   │   │
│  │     ORDER BY priority_weight DESC                            │   │
│  │     LIMIT 32                                                  │   │
│  │     FOR UPDATE SKIP LOCKED;  ← Skip rows locked by others   │   │
│  │                                                               │   │
│  │  2. Update selected tasks: state = 'running'                 │   │
│  │                                                               │   │
│  │  3. Send to executor (Celery/K8s/Local)                     │   │
│  │                                                               │   │
│  │  4. Release locks (transaction commit)                       │   │
│  │                                                               │   │
│  │  Result: Each task assigned to exactly one scheduler         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Scheduler Distribution:                                            │
│                                                                      │
│  Scheduler A locks:    Scheduler B locks:    Scheduler C locks:    │
│  ┌────────────────┐   ┌────────────────┐   ┌────────────────┐     │
│  │ task_1         │   │ task_2         │   │ task_3         │     │
│  │ task_4         │   │ task_5         │   │ task_6         │     │
│  │ task_7         │   │ task_8         │   │ task_9         │     │
│  └────────────────┘   └────────────────┘   └────────────────┘     │
│                                                                      │
│  If Scheduler A dies: tasks_1,4,7 remain 'queued'                  │
│  Other schedulers pick them up next iteration                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Executor Types / Типы Executor

### Comparison / Сравнение

```
┌─────────────────────────────────────────────────────────────────────┐
│  AIRFLOW EXECUTOR TYPES                                             │
│                                                                      │
│  LOCAL EXECUTOR (Development)                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ┌───────────┐                                               │   │
│  │  │ Scheduler │                                               │   │
│  │  │ + Executor│ ─→ subprocess ─→ Task 1                      │   │
│  │  │ (same     │ ─→ subprocess ─→ Task 2                      │   │
│  │  │  process) │ ─→ subprocess ─→ Task 3                      │   │
│  │  └───────────┘                                               │   │
│  │  Pros: Simple, no external dependencies                      │   │
│  │  Cons: Single machine, limited parallelism                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  CELERY EXECUTOR (Production)                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ┌───────────┐    ┌─────────────┐    ┌───────────────────┐ │   │
│  │  │ Scheduler │──▶│Redis/RabbitMQ│──▶│ Celery Workers    │ │   │
│  │  └───────────┘    └─────────────┘    │ ┌─────┐ ┌─────┐  │ │   │
│  │                                       │ │ W1  │ │ W2  │  │ │   │
│  │                                       │ └─────┘ └─────┘  │ │   │
│  │                                       └───────────────────┘ │   │
│  │  Pros: Distributed, scalable workers                        │   │
│  │  Cons: Requires broker (Redis/RabbitMQ)                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  KUBERNETES EXECUTOR (Cloud Native)                                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ┌───────────┐    ┌────────────────────────────────────┐   │   │
│  │  │ Scheduler │──▶│         Kubernetes API              │   │   │
│  │  └───────────┘    │  ┌─────────┐ ┌─────────┐ ┌───────┐│   │   │
│  │                    │  │ Pod     │ │ Pod     │ │ Pod   ││   │   │
│  │                    │  │ Task 1  │ │ Task 2  │ │Task 3 ││   │   │
│  │                    │  └─────────┘ └─────────┘ └───────┘│   │   │
│  │                    └────────────────────────────────────┘   │   │
│  │  Pros: Dynamic scaling, resource isolation per task         │   │
│  │  Cons: Pod startup latency (~10-30 seconds)                │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  CELERY + KUBERNETES EXECUTOR (Hybrid)                              │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Celery for fast, frequent tasks                            │   │
│  │  Kubernetes for resource-heavy tasks                        │   │
│  │  Best of both worlds                                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Executor Selection Guide / Руководство по выбору Executor

| Use Case | Recommended Executor |
|----------|---------------------|
| Development/Testing | LocalExecutor |
| Production (static workers) | CeleryExecutor |
| Kubernetes environment | KubernetesExecutor |
| Mixed workloads | CeleryKubernetesExecutor |
| Serverless (AWS) | ECSExecutor / MWAA |

---

## DAG Definition / Определение DAG

### Classic Approach / Классический подход

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'email_on_failure': True,
    'email': ['team@example.com'],
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='etl_pipeline',
    default_args=default_args,
    description='Daily ETL pipeline',
    schedule_interval='@daily',  # or '0 0 * * *' (cron)
    start_date=datetime(2024, 1, 1),
    catchup=False,  # Don't backfill
    tags=['etl', 'production'],
) as dag:

    extract = BashOperator(
        task_id='extract',
        bash_command='python /scripts/extract.py {{ ds }}',
    )

    def transform_fn(**context):
        # Access execution date
        execution_date = context['ds']
        # Process data
        return {'processed_rows': 1000}

    transform = PythonOperator(
        task_id='transform',
        python_callable=transform_fn,
        provide_context=True,
    )

    load = BashOperator(
        task_id='load',
        bash_command='python /scripts/load.py',
    )

    # Define dependencies
    extract >> transform >> load
```

### TaskFlow API (Airflow 2.x) / TaskFlow API (Airflow 2.x)

```python
from airflow.decorators import dag, task
from datetime import datetime

@dag(
    dag_id='taskflow_etl',
    schedule_interval='@daily',
    start_date=datetime(2024, 1, 1),
    catchup=False,
)
def etl_pipeline():

    @task()
    def extract() -> dict:
        """Extract data from source"""
        return {'data': [1, 2, 3, 4, 5]}

    @task()
    def transform(raw_data: dict) -> dict:
        """Transform data"""
        return {'transformed': [x * 2 for x in raw_data['data']]}

    @task()
    def load(transformed_data: dict):
        """Load data to destination"""
        print(f"Loading {len(transformed_data['transformed'])} records")

    # Automatic XCom passing
    raw = extract()
    transformed = transform(raw)
    load(transformed)

# Instantiate DAG
etl_dag = etl_pipeline()
```

### XCom (Cross-Communication) / XCom (Межзадачная коммуникация)

```
┌─────────────────────────────────────────────────────────────────────┐
│  XCOM - TASK DATA PASSING                                           │
│                                                                      │
│  XCom = Cross-Communication mechanism for passing data between tasks│
│  XCom = Механизм передачи данных между задачами                    │
│                                                                      │
│  ┌─────────────┐    XCom (DB)    ┌─────────────┐                   │
│  │   Task A    │ ──────────────▶ │   Task B    │                   │
│  │  (extract)  │   key: "data"   │ (transform) │                   │
│  └─────────────┘   value: {...}  └─────────────┘                   │
│                                                                      │
│  Manual XCom (classic):                                             │
│  # Push                                                             │
│  context['ti'].xcom_push(key='data', value={'rows': 100})          │
│  # Pull                                                             │
│  data = context['ti'].xcom_pull(task_ids='extract', key='data')    │
│                                                                      │
│  TaskFlow (automatic):                                              │
│  @task                                                              │
│  def extract() -> dict:                                             │
│      return {'rows': 100}  # Automatically pushed to XCom          │
│                                                                      │
│  @task                                                              │
│  def transform(data: dict):  # Automatically pulled from XCom      │
│      print(data['rows'])                                            │
│                                                                      │
│  LIMITATIONS:                                                       │
│  • XCom stored in metadata DB (not for large data!)                │
│  • Default limit: ~48KB (MySQL), ~1GB (PostgreSQL)                 │
│  • For large data: use S3/GCS paths instead                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Scheduling Concepts / Концепции планирования

### Execution Date vs Start Date / Дата выполнения vs Дата старта

```
┌─────────────────────────────────────────────────────────────────────┐
│  AIRFLOW DATE CONCEPTS                                              │
│                                                                      │
│  DAG: schedule_interval='@daily', start_date='2024-01-01'          │
│                                                                      │
│  Timeline:                                                          │
│  ─────────────────────────────────────────────────────────────────  │
│  Jan 1      Jan 2      Jan 3      Jan 4      Jan 5                 │
│  ├──────────┼──────────┼──────────┼──────────┼──────────           │
│  │          │          │          │          │                      │
│  │          ▼          ▼          ▼          ▼                      │
│  │       Run 1      Run 2      Run 3      Run 4                    │
│  │       exec_date  exec_date  exec_date  exec_date                │
│  │       Jan 1      Jan 2      Jan 3      Jan 4                    │
│  │                                                                  │
│  │   execution_date = start of interval being processed            │
│  │   Actual run time = end of interval + schedule_interval         │
│  │                                                                  │
│  │   Run for Jan 1 data actually runs at 00:00 Jan 2               │
│  └──────────────────────────────────────────────────────────────    │
│                                                                      │
│  Why? "Process yesterday's data" pattern                           │
│  execution_date = "data date", not "run date"                      │
│                                                                      │
│  Airflow 2.2+ uses "data_interval_start" / "data_interval_end"     │
│  for clarity                                                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Catchup and Backfill / Catchup и Backfill

```
┌─────────────────────────────────────────────────────────────────────┐
│  CATCHUP AND BACKFILL                                               │
│                                                                      │
│  CATCHUP (catchup=True/False):                                      │
│  When DAG is deployed with start_date in the past                  │
│                                                                      │
│  catchup=True (default):                                            │
│  ─────────────────────────────────────────────────────────────────  │
│  start_date    today                                                │
│  Jan 1         Jan 10                                               │
│  ├──────────────┤                                                   │
│  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼  ▼                                     │
│  Run all 9 missed intervals (could overwhelm system!)              │
│                                                                      │
│  catchup=False:                                                     │
│  ─────────────────────────────────────────────────────────────────  │
│  Only run latest interval (Jan 9 data)                             │
│  ▼                                                                  │
│                                                                      │
│  BACKFILL (manual command):                                         │
│  airflow dags backfill -s 2024-01-01 -e 2024-01-05 my_dag          │
│  Manually trigger runs for historical dates                        │
│  Useful for reprocessing after code changes                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Production Best Practices / Best Practices для Production

### DAG Design Guidelines / Рекомендации по дизайну DAG

```
┌─────────────────────────────────────────────────────────────────────┐
│  AIRFLOW BEST PRACTICES                                             │
│                                                                      │
│  1. KEEP DAGs LIGHTWEIGHT                                           │
│     • Move heavy logic to external scripts                         │
│     • DAG file should parse quickly (< 30 sec)                    │
│     • Avoid database calls at parse time                           │
│                                                                      │
│  2. IDEMPOTENT TASKS                                                │
│     • Re-running should produce same result                        │
│     • Use INSERT ... ON CONFLICT DO UPDATE                         │
│     • Don't rely on external state                                 │
│                                                                      │
│  3. ATOMIC TASKS                                                    │
│     • Each task does one thing                                     │
│     • Easier to retry and debug                                    │
│     • Avoid mega-tasks                                              │
│                                                                      │
│  4. USE CONNECTIONS AND VARIABLES                                   │
│     • Don't hardcode credentials                                    │
│     • Store in Airflow Connections (encrypted)                     │
│     • Use Variables for config                                     │
│                                                                      │
│  5. SET APPROPRIATE TIMEOUTS                                        │
│     execution_timeout=timedelta(hours=2)                           │
│     dagrun_timeout=timedelta(hours=6)                              │
│                                                                      │
│  6. USE TASK GROUPS FOR ORGANIZATION                                │
│     with TaskGroup("load_data") as load_group:                     │
│         load_users = PythonOperator(...)                           │
│         load_events = PythonOperator(...)                          │
└─────────────────────────────────────────────────────────────────────┘
```

### Scaling Airflow / Масштабирование Airflow

```
┌─────────────────────────────────────────────────────────────────────┐
│  AIRFLOW SCALING STRATEGIES                                         │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  HORIZONTAL SCALING                                          │   │
│  │                                                               │   │
│  │  Component      │ Strategy                                   │   │
│  │  ───────────────┼───────────────────────────────────────── │   │
│  │  Scheduler      │ Run 2-3 instances (HA)                    │   │
│  │  Web Server     │ Run behind load balancer                  │   │
│  │  Workers        │ Add more Celery/K8s workers               │   │
│  │  DAG Processor  │ Increase parallelism config               │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  KEY CONFIGURATION                                           │   │
│  │                                                               │   │
│  │  [core]                                                      │   │
│  │  parallelism = 32           # Total concurrent tasks        │   │
│  │  dag_concurrency = 16       # Tasks per DAG                 │   │
│  │  max_active_runs_per_dag = 4                                │   │
│  │                                                               │   │
│  │  [scheduler]                                                 │   │
│  │  parsing_processes = 4      # DAG parsing parallelism       │   │
│  │  min_file_process_interval = 30  # Seconds between parses  │   │
│  │                                                               │   │
│  │  [celery]                                                    │   │
│  │  worker_concurrency = 16    # Tasks per worker              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  PERFORMANCE TARGETS (2.x):                                         │
│  • 1000+ DAGs per cluster                                          │
│  • 10,000+ task instances per day                                  │
│  • < 5 second scheduling latency                                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Airflow vs Alternatives / Airflow vs Альтернативы

| Feature | Airflow | [[Temporal]] | [[Conductor]] |
|---------|---------|----------|-----------|
| **Primary Use Case** | Data pipelines | Business workflows | Microservice orchestration |
| **Scheduling** | Cron-based | Event-driven | Event-driven |
| **Definition** | Python DAGs | Code (multi-lang) | JSON |
| **State Model** | Task status in DB | Event Sourcing | Task status |
| **Long Running** | Limited (timeouts) | Native (days/weeks) | Limited |
| **HA** | Multi-scheduler | History Shards | Stateless servers |
| **Community** | Very large | Growing fast | Moderate |
| **Cloud Options** | MWAA, Astronomer | Temporal Cloud | Orkes |

### When to Choose Airflow / Когда выбирать Airflow

**Choose Airflow when / Выбирайте Airflow когда:**
- ETL/ELT data pipelines
- Batch processing with schedules
- ML training pipelines
- Team knows Python well
- Need extensive operator ecosystem

**Don't choose Airflow when / Не выбирайте Airflow когда:**
- Real-time event processing
- Long-running business workflows
- Complex branching logic
- Sub-minute scheduling needs

## Связано с
- [[Orchestration]]
- [[Temporal]]

## Ресурсы
- [Apache Airflow Documentation](https://airflow.apache.org/docs/)
- [Airflow Best Practices](https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html)
- [Airflow 2.0: DAG Serialization](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/dag-serialization.html)
- [Airflow HA Scheduler](https://airflow.apache.org/docs/apache-airflow/stable/administration-and-deployment/scheduler.html)
- [Astronomer Blog](https://www.astronomer.io/blog/)

---
tags:
  - system-design
  - orchestration
  - netflix
created: 2026-02-17
---

# Архитектура Netflix Conductor

## Что это
Netflix Conductor -- движок оркестрации с открытым исходным кодом (2016) для координации микросервисов. Использует JSON-определения workflow и визуальный UI для отладки. Разработан Netflix для обработки медиа-контента (транскодирование, DRM, упаковка).

## What is Netflix Conductor? / Что такое Netflix Conductor?

**Netflix Conductor** is an open-source orchestration engine developed by Netflix (2016) for coordinating microservices. It uses **JSON-based workflow definitions** and provides a visual UI for debugging.

**Netflix Conductor** -- это движок оркестрации с открытым исходным кодом, разработанный Netflix (2016) для координации микросервисов. Использует **определения workflow на JSON** и предоставляет визуальный UI для отладки.

### Why Netflix Built Conductor / Почему Netflix создали Conductor

```
┌─────────────────────────────────────────────────────────────────────┐
│  NETFLIX'S CHALLENGE (2016)                                         │
│                                                                      │
│  Media Processing Pipeline:                                         │
│                                                                      │
│  Upload → Transcode → Quality Check → Encrypt → Package → Publish  │
│             ↓                                                        │
│        [Multiple renditions: 4K, 1080p, 720p, 480p]                │
│             ↓                                                        │
│        [Multiple codecs: H.264, H.265, VP9, AV1]                   │
│             ↓                                                        │
│        [Multiple DRM: Widevine, FairPlay, PlayReady]               │
│                                                                      │
│  Problem: Thousands of microservices, millions of daily workflows   │
│  Need: Declarative workflow definition, visual debugging            │
│                                                                      │
│  Solution: Conductor - JSON workflows with built-in UI              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Architecture Overview / Обзор архитектуры

### High-Level Components / Высокоуровневые компоненты

```
┌─────────────────────────────────────────────────────────────────────┐
│                      CONDUCTOR ARCHITECTURE                         │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    CONDUCTOR SERVER                          │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │   │
│  │  │   REST API   │  │ Workflow     │  │   Task       │      │   │
│  │  │   Gateway    │  │ Execution    │  │   Queues     │      │   │
│  │  │              │  │ Service      │  │   Service    │      │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘      │   │
│  │         │                 │                 │               │   │
│  │         └─────────────────┼─────────────────┘               │   │
│  │                           ▼                                  │   │
│  │              ┌──────────────────────┐                       │   │
│  │              │    Persistence       │                       │   │
│  │              │  (Redis/Dynamo/PG)   │                       │   │
│  │              └──────────────────────┘                       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │  Worker 1   │  │  Worker 2   │  │  Worker N   │                 │
│  │  (Python)   │  │  (Java)     │  │  (Go)       │                 │
│  └─────────────┘  └─────────────┘  └─────────────┘                 │
│                                                                      │
│  Workers poll for tasks via REST API (language-agnostic)           │
└─────────────────────────────────────────────────────────────────────┘
```

### Core Concepts / Основные концепции

| Concept | Description (EN) | Описание (RU) |
|---------|------------------|---------------|
| **Workflow Definition** | JSON schema defining task sequence | JSON-схема, определяющая последовательность задач |
| **Task Definition** | Reusable task template with timeout/retry | Переиспользуемый шаблон задачи с таймаутами |
| **Task** | Instance of task definition in workflow | Экземпляр определения задачи в workflow |
| **Worker** | Process that executes tasks | Процесс, выполняющий задачи |
| **Task Queue** | Queue of pending tasks by type | Очередь ожидающих задач по типу |

---

## Workflow Definition / Определение Workflow

### JSON Structure / Структура JSON

```json
{
  "name": "video_processing_workflow",
  "description": "Process uploaded video through encoding pipeline",
  "version": 1,
  "schemaVersion": 2,
  "ownerEmail": "team@example.com",
  "tasks": [
    {
      "name": "validate_input",
      "taskReferenceName": "validate_input_ref",
      "type": "SIMPLE",
      "inputParameters": {
        "videoId": "${workflow.input.videoId}"
      }
    },
    {
      "name": "fork_encoding",
      "taskReferenceName": "fork_encoding_ref",
      "type": "FORK_JOIN",
      "forkTasks": [
        [
          {
            "name": "encode_1080p",
            "taskReferenceName": "encode_1080p_ref",
            "type": "SIMPLE"
          }
        ],
        [
          {
            "name": "encode_720p",
            "taskReferenceName": "encode_720p_ref",
            "type": "SIMPLE"
          }
        ]
      ]
    },
    {
      "name": "join_encoding",
      "taskReferenceName": "join_encoding_ref",
      "type": "JOIN",
      "joinOn": ["encode_1080p_ref", "encode_720p_ref"]
    },
    {
      "name": "package_hls",
      "taskReferenceName": "package_hls_ref",
      "type": "SIMPLE"
    }
  ],
  "outputParameters": {
    "hlsUrl": "${package_hls_ref.output.manifestUrl}"
  }
}
```

### Task Types / Типы задач

```
┌─────────────────────────────────────────────────────────────────────┐
│  CONDUCTOR TASK TYPES                                               │
│                                                                      │
│  SIMPLE:                                                            │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Regular task executed by worker                              │   │
│  │ • Polls task queue for work                                 │   │
│  │ • Returns output to Conductor                               │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  FORK_JOIN:                                                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │            ┌──► Task A ──┐                                  │   │
│  │   FORK ───►├──► Task B ──┼──► JOIN                         │   │
│  │            └──► Task C ──┘                                  │   │
│  │ Parallel execution of multiple branches                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  DECISION:                                                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    ┌──► Case A                              │   │
│  │   DECISION ───────►├──► Case B                              │   │
│  │   (switch/case)    └──► Default                             │   │
│  │ Conditional branching based on input                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  DYNAMIC:                                                           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │   Task type determined at runtime                            │   │
│  │   Useful for plugin-based architectures                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  SUB_WORKFLOW:                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │   Invoke another workflow as a task                          │   │
│  │   Enables workflow composition                               │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  HTTP:                                                              │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │   Built-in HTTP call (no worker needed)                     │   │
│  │   For simple API calls                                       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  WAIT:                                                              │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │   Wait for external signal or timeout                        │   │
│  │   Human-in-the-loop workflows                                │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Task Queue Architecture / Архитектура очередей задач

### Partitioned Queues / Партиционированные очереди

```
┌─────────────────────────────────────────────────────────────────────┐
│  CONDUCTOR TASK QUEUE MODEL                                         │
│                                                                      │
│  Task Type: "encode_video"                                          │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    TASK QUEUE PARTITIONS                     │   │
│  │                                                               │   │
│  │  Partition 0    Partition 1    Partition 2    Partition 3   │   │
│  │  ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐    │   │
│  │  │ Task A  │   │ Task D  │   │ Task G  │   │ Task J  │    │   │
│  │  │ Task B  │   │ Task E  │   │ Task H  │   │ Task K  │    │   │
│  │  │ Task C  │   │ Task F  │   │ Task I  │   │ Task L  │    │   │
│  │  └────┬────┘   └────┬────┘   └────┬────┘   └────┬────┘    │   │
│  │       │             │             │             │           │   │
│  │       ▼             ▼             ▼             ▼           │   │
│  │   Worker 1      Worker 2      Worker 3      Worker 4       │   │
│  │   (polls P0)    (polls P1)    (polls P2)    (polls P3)     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Distribution Strategy:                                             │
│  • Default: Round-robin across partitions                          │
│  • Custom: Based on task input (e.g., by videoId)                  │
│                                                                      │
│  Benefits:                                                          │
│  • Parallel processing across workers                               │
│  • No single queue bottleneck                                       │
│  • Easy horizontal scaling                                          │
└─────────────────────────────────────────────────────────────────────┘
```

### Worker Polling Model / Модель поллинга воркеров

```
┌─────────────────────────────────────────────────────────────────────┐
│  WORKER POLLING MECHANISM                                           │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                        WORKER                                │   │
│  │                                                               │   │
│  │  while True:                                                  │   │
│  │      # 1. Poll for tasks (batch)                             │   │
│  │      tasks = GET /api/tasks/poll/batch/{taskType}            │   │
│  │                ?count=10                                      │   │
│  │                &timeout=1000                                  │   │
│  │                &workerId=worker-1                             │   │
│  │                                                               │   │
│  │      for task in tasks:                                       │   │
│  │          # 2. Execute task                                    │   │
│  │          result = execute(task)                               │   │
│  │                                                               │   │
│  │          # 3. Report completion                               │   │
│  │          POST /api/tasks                                      │   │
│  │          {                                                    │   │
│  │              "workflowInstanceId": "...",                    │   │
│  │              "taskId": "...",                                │   │
│  │              "status": "COMPLETED",                          │   │
│  │              "outputData": { ... }                           │   │
│  │          }                                                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Long Polling:                                                      │
│  • Worker waits up to `timeout` ms for tasks                       │
│  • Reduces API calls when queue is empty                           │
│  • Server pushes tasks as soon as available                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Persistence Options / Варианты хранилищ

### Supported Backends / Поддерживаемые бэкенды

```
┌─────────────────────────────────────────────────────────────────────┐
│  CONDUCTOR PERSISTENCE BACKENDS                                     │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  REDIS (Default)                                             │   │
│  │  • Best for: Development, small deployments                 │   │
│  │  • Limitations: Memory-bound, single-node persistence       │   │
│  │  • Performance: Very fast, low latency                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  DYNAMO DB (Netflix Production)                              │   │
│  │  • Best for: AWS deployments, auto-scaling                  │   │
│  │  • Benefits: Managed, highly available                       │   │
│  │  • Limitations: AWS vendor lock-in                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  POSTGRESQL                                                  │   │
│  │  • Best for: On-premise, cloud-agnostic                     │   │
│  │  • Benefits: ACID, familiar, good tooling                   │   │
│  │  • Limitations: Manual sharding for scale                   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  ELASTICSEARCH (Event Indexing)                              │   │
│  │  • Used alongside primary persistence                        │   │
│  │  • Enables workflow search and analytics                    │   │
│  │  • Powers the Conductor UI search                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Model / Модель данных

```
┌─────────────────────────────────────────────────────────────────────┐
│  CONDUCTOR DATA MODEL                                               │
│                                                                      │
│  workflow_def                    task_def                           │
│  ┌─────────────────────┐        ┌─────────────────────┐            │
│  │ name (PK)           │        │ name (PK)           │            │
│  │ version             │        │ timeoutSeconds      │            │
│  │ tasks[] (JSON)      │        │ retryCount          │            │
│  │ inputParameters     │        │ retryDelaySeconds   │            │
│  │ outputParameters    │        │ responseTimeoutSec  │            │
│  └─────────────────────┘        └─────────────────────┘            │
│                                                                      │
│  workflow                        task                               │
│  ┌─────────────────────┐        ┌─────────────────────┐            │
│  │ workflowId (PK)     │        │ taskId (PK)         │            │
│  │ workflowName        │        │ workflowId (FK)     │            │
│  │ status              │        │ taskType            │            │
│  │ input (JSON)        │        │ status              │            │
│  │ output (JSON)       │        │ inputData (JSON)    │            │
│  │ startTime           │        │ outputData (JSON)   │            │
│  │ endTime             │        │ startTime           │            │
│  │ tasks[]             │        │ endTime             │            │
│  └─────────────────────┘        │ retryCount          │            │
│                                  └─────────────────────┘            │
│                                                                      │
│  event_execution                                                    │
│  ┌─────────────────────┐                                           │
│  │ eventId (PK)        │                                           │
│  │ workflowId          │                                           │
│  │ taskId              │                                           │
│  │ eventType           │                                           │
│  │ timestamp           │                                           │
│  │ payload (JSON)      │                                           │
│  └─────────────────────┘                                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Conductor UI / Пользовательский интерфейс

### Visual Workflow Debugging / Визуальная отладка workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│  CONDUCTOR UI FEATURES                                              │
│                                                                      │
│  Workflow List View:                                                │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Search: [video_processing_*____________] [Status ▼] [Search]│   │
│  │                                                               │   │
│  │ ID              | Name                 | Status    | Time    │   │
│  │ ────────────────┼──────────────────────┼───────────┼──────── │   │
│  │ abc-123         | video_processing     | COMPLETED | 5m 23s  │   │
│  │ def-456         | video_processing     | RUNNING   | 2m 10s  │   │
│  │ ghi-789         | video_processing     | FAILED    | 1m 45s  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Workflow Detail View:                                              │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                                                               │   │
│  │    [validate] → [FORK] → [encode_1080p] → [JOIN] → [package]│   │
│  │                     ↘   [encode_720p]  ↗                    │   │
│  │                          ↓ FAILED                            │   │
│  │                                                               │   │
│  │  Task: encode_720p                                           │   │
│  │  Status: FAILED                                              │   │
│  │  Error: "FFmpeg exit code 1: Invalid codec"                 │   │
│  │  Input: { "videoId": "123", "profile": "720p" }             │   │
│  │  Retry: [Retry Task] [Skip Task]                            │   │
│  │                                                               │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Key Actions:                                                       │
│  • Pause/Resume workflow                                            │
│  • Retry failed task                                                │
│  • Skip task (continue to next)                                     │
│  • Terminate workflow                                               │
│  • Restart from beginning                                           │
│  • View input/output at each step                                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Scalability / Масштабируемость

### Conductor Scaling Model / Модель масштабирования

```
┌─────────────────────────────────────────────────────────────────────┐
│  SCALING CONDUCTOR                                                  │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  CONDUCTOR SERVER CLUSTER                                    │   │
│  │                                                               │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐            │   │
│  │  │ Server 1   │  │ Server 2   │  │ Server 3   │            │   │
│  │  │ (Stateless)│  │ (Stateless)│  │ (Stateless)│            │   │
│  │  └────────────┘  └────────────┘  └────────────┘            │   │
│  │        │               │               │                    │   │
│  │        └───────────────┼───────────────┘                    │   │
│  │                        ▼                                     │   │
│  │               ┌─────────────────┐                           │   │
│  │               │  Load Balancer  │                           │   │
│  │               └─────────────────┘                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  Scaling Dimensions:                                                │
│  ┌───────────────┬─────────────────────────────────────────────┐   │
│  │ Component     │ Scaling Approach                            │   │
│  ├───────────────┼─────────────────────────────────────────────┤   │
│  │ Server        │ Add replicas (stateless)                    │   │
│  │ Workers       │ Add replicas per task type                  │   │
│  │ Task Queues   │ Increase partitions                         │   │
│  │ Persistence   │ Shard database / use DynamoDB               │   │
│  │ Search        │ Elasticsearch cluster scaling               │   │
│  └───────────────┴─────────────────────────────────────────────┘   │
│                                                                      │
│  Netflix Scale (2020):                                              │
│  • 10 million+ workflow executions per day                         │
│  • 100+ task types                                                  │
│  • Sub-second task dispatch latency                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Conductor vs [[Temporal]] / Conductor vs Temporal

### Comparison / Сравнение

| Aspect | Conductor | [[Temporal]] |
|--------|-----------|----------|
| **Workflow Definition** | JSON (declarative) | Code (imperative) |
| **Language Support** | Any (REST API) | SDK required (Go, Java, Python, TS) |
| **State Model** | Task status tracking | Event Sourcing |
| **Replay** | No automatic replay | Full deterministic replay |
| **Learning Curve** | Lower (JSON + REST) | Higher (SDK concepts) |
| **Debugging** | Built-in UI | Web UI + tctl CLI |
| **Long Timers** | Limited support | Native durable timers |
| **Complex Logic** | Cumbersome in JSON | Natural in code |
| **Community** | Moderate | Very active |
| **Cloud Offering** | Orkes Cloud | Temporal Cloud |

### When to Choose Conductor / Когда выбирать Conductor

**Choose Conductor when / Выбирайте Conductor когда:**
- Team prefers declarative JSON over code
- Need language-agnostic workers (REST API)
- Visual debugging is critical
- Simpler workflows without complex branching
- Netflix-style media processing pipelines

**Choose [[Temporal]] when / Выбирайте [[Temporal]] когда:**
- Complex business logic with many branches
- Long-running workflows (days/weeks)
- Need deterministic replay for debugging
- Team comfortable with SDK model
- Critical reliability requirements

---

## Code Example: Python Worker / Пример кода: Python Worker

```python
import time
import requests
from typing import Any, Dict

class ConductorWorker:
    def __init__(self, server_url: str, task_type: str, worker_id: str):
        self.server_url = server_url
        self.task_type = task_type
        self.worker_id = worker_id

    def poll_tasks(self, count: int = 1, timeout: int = 1000) -> list:
        """Poll for tasks from Conductor server"""
        response = requests.get(
            f"{self.server_url}/api/tasks/poll/batch/{self.task_type}",
            params={
                "count": count,
                "timeout": timeout,
                "workerId": self.worker_id
            }
        )
        return response.json() if response.status_code == 200 else []

    def complete_task(self, task_id: str, workflow_id: str, output: Dict[str, Any]):
        """Report task completion to Conductor"""
        requests.post(
            f"{self.server_url}/api/tasks",
            json={
                "workflowInstanceId": workflow_id,
                "taskId": task_id,
                "status": "COMPLETED",
                "outputData": output
            }
        )

    def fail_task(self, task_id: str, workflow_id: str, error: str):
        """Report task failure to Conductor"""
        requests.post(
            f"{self.server_url}/api/tasks",
            json={
                "workflowInstanceId": workflow_id,
                "taskId": task_id,
                "status": "FAILED",
                "reasonForIncompletion": error
            }
        )

    def run(self, execute_fn):
        """Main worker loop"""
        print(f"Worker {self.worker_id} started for task type: {self.task_type}")
        while True:
            tasks = self.poll_tasks(count=5, timeout=5000)
            for task in tasks:
                try:
                    result = execute_fn(task["inputData"])
                    self.complete_task(
                        task["taskId"],
                        task["workflowInstanceId"],
                        result
                    )
                except Exception as e:
                    self.fail_task(
                        task["taskId"],
                        task["workflowInstanceId"],
                        str(e)
                    )

# Usage
def encode_video(input_data: Dict[str, Any]) -> Dict[str, Any]:
    video_id = input_data["videoId"]
    profile = input_data["profile"]
    # ... actual encoding logic ...
    return {"encodedUrl": f"s3://bucket/{video_id}_{profile}.mp4"}

worker = ConductorWorker(
    server_url="http://localhost:8080",
    task_type="encode_video",
    worker_id="encoder-worker-1"
)
worker.run(encode_video)
```

## Связано с
- [[Orchestration]]
- [[Temporal]]

## Ресурсы
- [Netflix Conductor GitHub](https://github.com/Netflix/conductor)
- [Conductor Documentation](https://netflix.github.io/conductor/)
- [Netflix Blog: Evolution of Conductor](https://netflixtechblog.com/evolution-of-conductor-23e033e0a0d1)
- [Orkes Conductor (Commercial)](https://orkes.io/)
- [Conductor vs Temporal Comparison](https://temporal.io/blog/conductor-vs-temporal)

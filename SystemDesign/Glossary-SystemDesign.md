---
tags:
  - system-design
  - glossary
  - interview-prep
created: 2026-02-17
---

# Глоссарий терминов проектирования систем / Glossary of System Design Terms

## Что это

Глоссарий из 125+ терминов системного проектирования (EN/RU) по категориям: архитектура, оркестрация, брокеры сообщений, высокая доступность, консенсус, хранение данных, кэширование, сети, безопасность, наблюдаемость, DevOps.

---

## Table of Contents / Содержание

1. [General Architecture / Общая архитектура](#general-architecture--общая-архитектура)
2. [Orchestration / Оркестрация](#orchestration--оркестрация)
3. [Message Brokers / Брокеры сообщений](#message-brokers--брокеры-сообщений)
4. [High Availability / Высокая доступность](#high-availability--высокая-доступность)
5. [Data Storage / Хранение данных](#data-storage--хранение-данных)
6. [Networking / Сети](#networking--сети)
7. [Security / Безопасность](#security--безопасность)
8. [Observability / Наблюдаемость](#observability--наблюдаемость)
9. [DevOps & Infrastructure / DevOps и инфраструктура](#devops--infrastructure--devops-и-инфраструктура)

---

## General Architecture / Общая архитектура

| Term (EN) | Термин (RU) | Definition / Определение |
|-----------|-------------|--------------------------|
| **Microservices** | Микросервисы | Architectural style where application is composed of small, independent services communicating over network. / Архитектурный стиль, где приложение состоит из небольших независимых сервисов, взаимодействующих по сети. |
| **Monolith** | Монолит | Single, unified application where all components are interconnected and deployed together. / Единое приложение, где все компоненты связаны и развёртываются вместе. |
| **SOA (Service-Oriented Architecture)** | Сервис-ориентированная архитектура | Design pattern where services are provided through network protocols. Predecessor to microservices. / Паттерн проектирования, где сервисы предоставляются через сетевые протоколы. Предшественник микросервисов. |
| **API (Application Programming Interface)** | Программный интерфейс приложения | Contract defining how software components interact. / Контракт, определяющий взаимодействие программных компонентов. |
| **REST (Representational State Transfer)** | REST | Architectural style for web APIs using HTTP methods (GET, POST, PUT, DELETE). / Архитектурный стиль для веб-API, использующий HTTP-методы. |
| **gRPC (gRPC Remote Procedure Call)** | gRPC | High-performance RPC framework using Protocol Buffers. / Высокопроизводительный RPC-фреймворк на основе Protocol Buffers. |
| **BFF (Backend for Frontend)** | Бэкенд для фронтенда | Pattern where each frontend has a dedicated backend service. / Паттерн, где каждый фронтенд имеет выделенный бэкенд-сервис. |
| **SPOF (Single Point of Failure)** | Единая точка отказа | Component whose failure causes entire system to fail. / Компонент, отказ которого приводит к отказу всей системы. |
| **Horizontal Scaling** | Горизонтальное масштабирование | Adding more machines to handle increased load. / Добавление машин для обработки возросшей нагрузки. |
| **Vertical Scaling** | Вертикальное масштабирование | Adding more resources (CPU, RAM) to existing machine. / Добавление ресурсов (CPU, RAM) к существующей машине. |
| **Stateless** | Без состояния | Service that doesn't store client session data between requests. / Сервис, не хранящий данные сессии клиента между запросами. |
| **Stateful** | С состоянием | Service that maintains client session data between requests. / Сервис, сохраняющий данные сессии клиента между запросами. |
| **Idempotency** | Идемпотентность | Property where multiple identical requests produce same result as single request. / Свойство, при котором многократные идентичные запросы дают тот же результат, что и один запрос. |
| **Eventual Consistency** | Согласованность в конечном счёте | Consistency model where system becomes consistent over time. / Модель согласованности, при которой система становится согласованной со временем. |
| **Strong Consistency** | Строгая согласованность | Consistency model where all nodes see same data simultaneously. / Модель согласованности, при которой все узлы видят одинаковые данные одновременно. |

---

## Orchestration / Оркестрация

| Term (EN) | Термин (RU) | Definition / Определение |
|-----------|-------------|--------------------------|
| **Workflow** | Рабочий процесс | Sequence of steps to complete a task. / Последовательность шагов для выполнения задачи. |
| **Orchestrator** | Оркестратор | Service that coordinates execution of workflows. / Сервис, координирующий выполнение рабочих процессов. |
| **Task / Activity** | Задача / Активность | Single step in a workflow. / Один шаг в рабочем процессе. |
| **Worker** | Воркер / Исполнитель | Process that executes tasks. / Процесс, выполняющий задачи. |
| **DAG (Directed Acyclic Graph)** | Направленный ациклический граф | Graph structure used to represent workflow dependencies. No cycles allowed. / Структура графа для представления зависимостей в workflow. Циклы запрещены. |
| **Task Queue** | Очередь задач | Queue where tasks wait to be processed by workers. / Очередь, где задачи ждут обработки воркерами. |
| **Scheduler** | Планировщик | Component that decides when and where to run tasks. / Компонент, решающий когда и где запускать задачи. |
| **Event Sourcing** | Источник событий | Pattern where state changes are stored as sequence of events. / Паттерн, при котором изменения состояния хранятся как последовательность событий. |
| **Saga** | Сага | Pattern for managing distributed transactions across microservices. / Паттерн управления распределёнными транзакциями между микросервисами. |
| **Choreography** | Хореография | Saga pattern where services react to events without central coordinator. / Паттерн саги, где сервисы реагируют на события без центрального координатора. |
| **Orchestration (Saga)** | Оркестрация (Саги) | Saga pattern with central coordinator managing the flow. / Паттерн саги с центральным координатором, управляющим потоком. |
| **Durable Execution** | Надёжное выполнение | Execution model where workflow state survives failures. / Модель выполнения, при которой состояние workflow переживает сбои. |
| **History Shard** | Шард истории | Unit of concurrent workflow execution in Temporal. / Единица параллельного выполнения workflow в Temporal. |
| **Retry Policy** | Политика повторов | Configuration for how failed tasks should be retried. / Конфигурация повторных попыток для неудавшихся задач. |
| **Dead Letter Queue (DLQ)** | Очередь недоставленных сообщений | Queue for messages that couldn't be processed. / Очередь для сообщений, которые не удалось обработать. |

---

## Message Brokers / Брокеры сообщений

| Term (EN) | Термин (RU) | Definition / Определение |
|-----------|-------------|--------------------------|
| **Message Broker** | Брокер сообщений | Middleware for asynchronous communication between services. / Промежуточное ПО для асинхронной связи между сервисами. |
| **Topic** | Топик | Named channel for publishing messages. / Именованный канал для публикации сообщений. |
| **Partition** | Партиция / Секция | Subdivision of topic for parallel processing. / Подразделение топика для параллельной обработки. |
| **Offset** | Смещение | Position of message within partition. / Позиция сообщения внутри партиции. |
| **Consumer Group** | Группа потребителей | Set of consumers that divide partition processing. / Набор потребителей, разделяющих обработку партиций. |
| **Producer** | Продюсер / Производитель | Application that publishes messages to broker. / Приложение, публикующее сообщения в брокер. |
| **Consumer** | Консьюмер / Потребитель | Application that reads messages from broker. / Приложение, читающее сообщения из брокера. |
| **Rebalancing** | Ребалансировка | Process of redistributing partitions among consumers. / Процесс перераспределения партиций между консьюмерами. |
| **ISR (In-Sync Replicas)** | Синхронизированные реплики | Set of replicas fully caught up with leader. / Набор реплик, полностью синхронизированных с лидером. |
| **Acks (Acknowledgments)** | Подтверждения | Producer confirmation that message was received. / Подтверждение продюсером получения сообщения. |
| **Exactly-Once Semantics** | Семантика "ровно один раз" | Guarantee that message is processed exactly once. / Гарантия обработки сообщения ровно один раз. |
| **At-Least-Once** | Как минимум один раз | Guarantee that message is processed at least once (may duplicate). / Гарантия обработки сообщения хотя бы один раз (возможны дубли). |
| **At-Most-Once** | Не более одного раза | Guarantee that message is processed at most once (may be lost). / Гарантия обработки сообщения не более одного раза (может быть потеряно). |
| **Log Compaction** | Уплотнение лога | Retention policy keeping only latest value per key. / Политика хранения, сохраняющая только последнее значение по ключу. |
| **Backpressure** | Обратное давление | Mechanism to slow producers when consumers can't keep up. / Механизм замедления продюсеров, когда консьюмеры не успевают. |
| **Idempotent Producer** | Идемпотентный продюсер | Producer that prevents duplicate messages on retry. / Продюсер, предотвращающий дублирование при повторах. |
| **KRaft (Kafka Raft)** | KRaft (Kafka Raft) | Kafka's built-in consensus protocol replacing ZooKeeper. / Встроенный протокол консенсуса Kafka, заменяющий ZooKeeper. |

---

## High Availability / Высокая доступность

| Term (EN) | Термин (RU) | Definition / Определение |
|-----------|-------------|--------------------------|
| **HA (High Availability)** | Высокая доступность | System design ensuring continuous operation. / Проектирование системы с обеспечением непрерывной работы. |
| **Failover** | Переключение при сбое | Automatic switch to backup system on failure. / Автоматическое переключение на резервную систему при сбое. |
| **Failback** | Возврат после сбоя | Return to primary system after recovery. / Возврат на основную систему после восстановления. |
| **RTO (Recovery Time Objective)** | Целевое время восстановления | Maximum acceptable downtime after failure. / Максимально допустимое время простоя после сбоя. |
| **RPO (Recovery Point Objective)** | Целевая точка восстановления | Maximum acceptable data loss measured in time. / Максимально допустимая потеря данных, измеряемая во времени. |
| **Active-Passive** | Активный-пассивный | HA pattern with one active and one standby node. / Паттерн HA с одним активным и одним резервным узлом. |
| **Active-Active** | Активный-активный | HA pattern where all nodes process requests. / Паттерн HA, где все узлы обрабатывают запросы. |
| **Leader Election** | Выбор лидера | Process of selecting one node to coordinate work. / Процесс выбора одного узла для координации работы. |
| **Load Distribution** | Распределение нагрузки | Dividing work among multiple nodes. / Разделение работы между несколькими узлами. |
| **Heartbeat** | Сердцебиение | Periodic signal indicating node is alive. / Периодический сигнал, указывающий что узел жив. |
| **Health Check** | Проверка здоровья | Mechanism to verify service is functioning. / Механизм проверки работоспособности сервиса. |
| **Circuit Breaker** | Предохранитель | Pattern preventing cascading failures. / Паттерн предотвращения каскадных сбоев. |
| **Bulkhead** | Переборка | Pattern isolating components to prevent system-wide failure. / Паттерн изоляции компонентов для предотвращения общего сбоя. |
| **Graceful Degradation** | Плавная деградация | System continues with reduced functionality during failure. / Система продолжает работать с ограниченной функциональностью при сбое. |
| **Quorum** | Кворум | Minimum number of nodes required for decision. / Минимальное число узлов, необходимое для принятия решения. |

---

## Consensus Algorithms / Алгоритмы консенсуса

| Term (EN) | Термин (RU) | Definition / Определение |
|-----------|-------------|--------------------------|
| **Consensus** | Консенсус | Agreement among distributed nodes on single value. / Согласие распределённых узлов относительно одного значения. |
| **Raft** | Raft | Understandable consensus algorithm using leader-based approach. / Понятный алгоритм консенсуса с подходом на основе лидера. |
| **Paxos** | Paxos | Original consensus algorithm, complex but foundational. / Оригинальный алгоритм консенсуса, сложный но фундаментальный. |
| **ZAB (Zookeeper Atomic Broadcast)** | ZAB | Consensus protocol used by Apache ZooKeeper. / Протокол консенсуса, используемый Apache ZooKeeper. |
| **Split Brain** | Разделение мозга | Failure mode where nodes disagree on leader. / Режим отказа, при котором узлы не согласны относительно лидера. |
| **Byzantine Fault** | Византийский сбой | Failure where node behaves maliciously or arbitrarily. / Сбой, при котором узел ведёт себя вредоносно или произвольно. |

---

## Data Storage / Хранение данных

| Term (EN) | Термин (RU) | Definition / Определение |
|-----------|-------------|--------------------------|
| **ACID** | ACID | Atomicity, Consistency, Isolation, Durability - transaction properties. / Атомарность, Согласованность, Изоляция, Долговечность - свойства транзакций. |
| **BASE** | BASE | Basically Available, Soft state, Eventually consistent - NoSQL properties. / Базовая доступность, Мягкое состояние, Согласованность в конечном счёте - свойства NoSQL. |
| **CAP Theorem** | Теорема CAP | Impossibility theorem: Consistency, Availability, Partition tolerance - pick two. / Теорема невозможности: Согласованность, Доступность, Устойчивость к разделению - выбери два. |
| **Sharding** | Шардирование | Horizontal partitioning of data across databases. / Горизонтальное разделение данных между базами данных. |
| **Replication** | Репликация | Copying data across multiple nodes. / Копирование данных на несколько узлов. |
| **Primary-Replica** | Основной-реплика | Replication with one writable primary and read-only replicas. / Репликация с одним записываемым основным и репликами только для чтения. |
| **Consistent Hashing** | Консистентное хеширование | Hash technique minimizing redistribution on node changes. / Техника хеширования, минимизирующая перераспределение при изменении узлов. |
| **Time Series Database** | База данных временных рядов | Database optimized for timestamped data. / База данных, оптимизированная для данных с временными метками. |
| **OLTP (Online Transaction Processing)** | Обработка транзакций | Workload pattern for transactional operations. / Паттерн нагрузки для транзакционных операций. |
| **OLAP (Online Analytical Processing)** | Аналитическая обработка | Workload pattern for analytical queries. / Паттерн нагрузки для аналитических запросов. |
| **Materialized View** | Материализованное представление | Pre-computed query result stored as table. / Предвычисленный результат запроса, хранимый как таблица. |
| **TTL (Time to Live)** | Время жизни | Expiration time for cached or stored data. / Время истечения для кэшированных или хранимых данных. |
| **Write-Ahead Log (WAL)** | Журнал упреждающей записи | Log of changes before they're applied to database. / Журнал изменений до их применения к базе данных. |
| **Connection Pooling** | Пул соединений | Reusing database connections to reduce overhead. / Переиспользование соединений с БД для снижения накладных расходов. |

---

## Caching / Кэширование

| Term (EN) | Термин (RU) | Definition / Определение |
|-----------|-------------|--------------------------|
| **Cache** | Кэш | Fast storage layer for frequently accessed data. / Быстрый слой хранения для часто запрашиваемых данных. |
| **Cache-Aside (Lazy Loading)** | Ленивое кэширование | Pattern where application manages cache reads/writes. / Паттерн, где приложение управляет чтением/записью кэша. |
| **Write-Through** | Сквозная запись | Pattern where cache is updated on every write. / Паттерн, где кэш обновляется при каждой записи. |
| **Write-Behind (Write-Back)** | Отложенная запись | Pattern where writes go to cache first, then to database. / Паттерн, где записи идут сначала в кэш, потом в БД. |
| **Cache Invalidation** | Инвалидация кэша | Process of marking cached data as stale. / Процесс пометки кэшированных данных как устаревших. |
| **Cache Eviction** | Вытеснение из кэша | Removing items from cache to free space. / Удаление элементов из кэша для освобождения места. |
| **LRU (Least Recently Used)** | Наименее недавно использованный | Eviction policy removing least recently accessed items. / Политика вытеснения, удаляющая наименее недавно использованные элементы. |
| **LFU (Least Frequently Used)** | Наименее часто используемый | Eviction policy removing least frequently accessed items. / Политика вытеснения, удаляющая наименее часто используемые элементы. |
| **Cache Stampede** | Массовый сброс кэша | Problem when many requests hit database simultaneously after cache expires. / Проблема, когда много запросов одновременно попадают в БД после истечения кэша. |
| **Distributed Cache** | Распределённый кэш | Cache spanning multiple nodes. / Кэш, распределённый между несколькими узлами. |

---

## Networking / Сети

| Term (EN) | Термин (RU) | Definition / Определение |
|-----------|-------------|--------------------------|
| **Load Balancer** | Балансировщик нагрузки | Distributes traffic across multiple servers. / Распределяет трафик между несколькими серверами. |
| **L4 Load Balancing** | Балансировка уровня 4 | Load balancing at transport layer (TCP/UDP). / Балансировка на транспортном уровне (TCP/UDP). |
| **L7 Load Balancing** | Балансировка уровня 7 | Load balancing at application layer (HTTP). / Балансировка на уровне приложения (HTTP). |
| **Round Robin** | Циклический перебор | Algorithm distributing requests evenly in rotation. / Алгоритм равномерного распределения запросов по кругу. |
| **Least Connections** | Наименьшее число соединений | Algorithm routing to server with fewest connections. / Алгоритм маршрутизации на сервер с наименьшим числом соединений. |
| **DNS (Domain Name System)** | Система доменных имён | System translating domain names to IP addresses. / Система преобразования доменных имён в IP-адреса. |
| **GeoDNS** | Географический DNS | DNS returning different IPs based on client location. / DNS, возвращающий разные IP в зависимости от местоположения клиента. |
| **CDN (Content Delivery Network)** | Сеть доставки контента | Distributed servers caching content close to users. / Распределённые серверы, кэширующие контент близко к пользователям. |
| **Edge Server** | Пограничный сервер | CDN server located near end users. / Сервер CDN, расположенный близко к конечным пользователям. |
| **Reverse Proxy** | Обратный прокси | Server forwarding client requests to backend servers. / Сервер, перенаправляющий запросы клиентов на бэкенд-серверы. |
| **API Gateway** | API-шлюз | Entry point managing API traffic. / Точка входа, управляющая API-трафиком. |
| **Apache APISIX** | Apache APISIX | High-performance API gateway with radix tree routing, multi-language plugins (Lua/Python/Go/Java/WASM), etcd-based config. / Высокопроизводительный API-шлюз с маршрутизацией radix tree, мультиязычными плагинами, конфигурацией через etcd. |
| **etcd** | etcd | Distributed key-value store for shared configuration and service discovery. Used by Kubernetes and APISIX. / Распределённое хранилище ключ-значение для конфигурации и обнаружения сервисов. Используется Kubernetes и APISIX. |
| **Radix Tree** | Префиксное дерево (radix) | Compressed trie data structure for O(k) string lookup (k = key length). Used by APISIX for route matching. / Сжатая структура trie для O(k) поиска строк. Используется APISIX для маршрутизации. |
| **Rate Limiting** | Ограничение частоты | Controlling request rate to prevent abuse. / Контроль частоты запросов для предотвращения злоупотреблений. |
| **Throttling** | Дросселирование | Limiting resource usage rate. / Ограничение скорости использования ресурсов. |

---

## Security / Безопасность

| Term (EN) | Термин (RU) | Definition / Определение |
|-----------|-------------|--------------------------|
| **AuthN (Authentication)** | Аутентификация | Verifying identity of user or service. / Проверка подлинности пользователя или сервиса. |
| **AuthZ (Authorization)** | Авторизация | Determining what authenticated user can access. / Определение, к чему имеет доступ аутентифицированный пользователь. |
| **OAuth 2.0** | OAuth 2.0 | Authorization framework for delegated access. / Фреймворк авторизации для делегированного доступа. |
| **OIDC (OpenID Connect)** | OpenID Connect | Identity layer on top of OAuth 2.0. / Слой идентификации поверх OAuth 2.0. |
| **JWT (JSON Web Token)** | JWT | Compact, URL-safe token for claims between parties. / Компактный, URL-безопасный токен для утверждений между сторонами. |
| **RBAC (Role-Based Access Control)** | Управление доступом на основе ролей | Access control based on user roles. / Контроль доступа на основе ролей пользователей. |
| **ABAC (Attribute-Based Access Control)** | Управление доступом на основе атрибутов | Access control based on attributes (user, resource, environment). / Контроль доступа на основе атрибутов (пользователь, ресурс, окружение). |
| **TLS (Transport Layer Security)** | Протокол защиты транспортного уровня | Cryptographic protocol for secure communication. / Криптографический протокол для безопасной связи. |
| **mTLS (Mutual TLS)** | Взаимный TLS | TLS with client and server certificate verification. / TLS с проверкой сертификатов клиента и сервера. |
| **Encryption at Rest** | Шифрование данных в покое | Encrypting stored data. / Шифрование хранимых данных. |
| **Encryption in Transit** | Шифрование данных при передаче | Encrypting data during transmission. / Шифрование данных при передаче. |
| **OWASP (Open Web Application Security Project)** | OWASP | Organization providing security guidance and top 10 vulnerabilities. / Организация, предоставляющая руководства по безопасности и топ-10 уязвимостей. |
| **Multi-tenancy** | Мультитенантность | Architecture serving multiple customers from single deployment. / Архитектура обслуживания нескольких клиентов из единого развёртывания. |

---

## Observability / Наблюдаемость

| Term (EN) | Термин (RU) | Definition / Определение |
|-----------|-------------|--------------------------|
| **Observability** | Наблюдаемость | Ability to understand system state from external outputs. / Способность понимать состояние системы по внешним выходным данным. |
| **Three Pillars** | Три столпа | Metrics, Logs, Traces - core observability signals. / Метрики, Логи, Трейсы - основные сигналы наблюдаемости. |
| **Metrics** | Метрики | Numeric measurements over time. / Числовые измерения во времени. |
| **Logs** | Логи | Timestamped records of events. / Записи событий с временными метками. |
| **Traces** | Трейсы | Records of request path through distributed system. / Записи пути запроса через распределённую систему. |
| **Span** | Спан | Single operation within a trace. / Одна операция внутри трейса. |
| **Distributed Tracing** | Распределённая трассировка | Following requests across multiple services. / Отслеживание запросов через несколько сервисов. |
| **Context Propagation** | Распространение контекста | Passing trace context between services. / Передача контекста трейса между сервисами. |
| **SLO (Service Level Objective)** | Целевой уровень сервиса | Target for service reliability metrics. / Цель для метрик надёжности сервиса. |
| **SLI (Service Level Indicator)** | Индикатор уровня сервиса | Metric measuring service level. / Метрика, измеряющая уровень сервиса. |
| **SLA (Service Level Agreement)** | Соглашение об уровне сервиса | Contract specifying service level commitment. / Контракт, определяющий обязательства по уровню сервиса. |
| **P99 Latency** | Латентность P99 | 99th percentile response time. / 99-й перцентиль времени ответа. |
| **Alerting** | Алертинг | Notification when metrics exceed thresholds. / Уведомление при превышении порогов метрик. |
| **Dashboard** | Дашборд | Visual display of metrics and status. / Визуальное отображение метрик и статуса. |
| **ELK (Elasticsearch, Logstash, Kibana)** | ELK-стек | Popular log aggregation stack: search engine, pipeline, visualization. / Популярный стек агрегации логов: поисковый движок, пайплайн, визуализация. |

---

## DevOps & Infrastructure / DevOps и инфраструктура

| Term (EN) | Термин (RU) | Definition / Определение |
|-----------|-------------|--------------------------|
| **CI/CD (Continuous Integration/Continuous Delivery)** | Непрерывная интеграция/доставка | Practice of automating build, test, and deployment. / Практика автоматизации сборки, тестирования и развёртывания. |
| **Container** | Контейнер | Lightweight, isolated environment for running applications. / Лёгкая, изолированная среда для запуска приложений. |
| **Docker** | Docker | Platform for building and running containers. / Платформа для создания и запуска контейнеров. |
| **Kubernetes (K8s)** | Kubernetes | Container orchestration platform. / Платформа оркестрации контейнеров. |
| **Pod** | Под | Smallest deployable unit in Kubernetes. / Наименьшая развёртываемая единица в Kubernetes. |
| **Deployment** | Деплоймент | Kubernetes resource for managing application replicas. / Ресурс Kubernetes для управления репликами приложения. |
| **Service (K8s)** | Сервис (K8s) | Kubernetes resource for network access to pods. / Ресурс Kubernetes для сетевого доступа к подам. |
| **HPA (Horizontal Pod Autoscaler)** | Горизонтальный автоскейлер подов | Kubernetes resource for automatic scaling. / Ресурс Kubernetes для автоматического масштабирования. |
| **Namespace** | Пространство имён | Kubernetes resource for isolating resources. / Ресурс Kubernetes для изоляции ресурсов. |
| **IaC (Infrastructure as Code)** | Инфраструктура как код | Managing infrastructure through code. / Управление инфраструктурой через код. |
| **GitOps** | GitOps | Using Git as single source of truth for infrastructure. / Использование Git как единого источника истины для инфраструктуры. |
| **Blue-Green Deployment** | Сине-зелёное развёртывание | Deployment strategy with two identical environments. / Стратегия развёртывания с двумя идентичными окружениями. |
| **Canary Deployment** | Канареечное развёртывание | Gradual rollout to subset of users. / Постепенное развёртывание для части пользователей. |
| **Rolling Update** | Постепенное обновление | Updating instances one at a time. / Обновление инстансов по одному. |

---

## Polyvision-Specific Terms / Термины Polyvision

| Term (EN) | Термин (RU) | Definition / Определение |
|-----------|-------------|--------------------------|
| **Panorama** | Панорама | Stitched video from left and right cameras (5700x1669). / Сшитое видео с левой и правой камер (5700x1669). |
| **VirtualCam** | Виртуальная камера | Generated perspective view from panorama. / Сгенерированный ракурсный вид из панорамы. |
| **Tile** | Тайл | Section of panorama for detection processing. / Секция панорамы для обработки детекции. |
| **Detection** | Детекция | Identified object (player, ball, referee) with bounding box. / Идентифицированный объект (игрок, мяч, судья) с ограничивающей рамкой. |
| **Trajectory** | Траектория | Path of object across frames. / Путь объекта через кадры. |
| **Calibration** | Калибровка | Camera parameters for stitching and perspective correction. / Параметры камеры для сшивки и коррекции перспективы. |
| **LUT (Lookup Table)** | Таблица преобразования | Pre-computed transformation for fast warping. / Предвычисленное преобразование для быстрой деформации. |
| **Processing Job** | Задача обработки | Full pipeline execution for one match. / Полное выполнение конвейера для одного матча. |
| **Match Manifest** | Манифест матча | Metadata file describing uploaded recordings. / Файл метаданных, описывающий загруженные записи. |
| **Nonce** | Одноразовое число | One-time random value used to prevent replay attacks. Stored in Redis with 5-min TTL, consumed atomically via GETDEL. / Одноразовое случайное значение для предотвращения повторных атак. Хранится в Redis с TTL 5 мин, потребляется атомарно через GETDEL. |
| **Ed25519** | Ed25519 | Edwards-curve digital signature algorithm used for device authentication in Polyvision. / Алгоритм цифровой подписи на эллиптических кривых Эдвардса для аутентификации устройств. |

---

*Total terms: 125+ | Всего терминов: 125+*

*Last updated: 2026-02-17*

---

## Связано с

- [[Resources/Books]]
- [[Resources/Courses]]
- [[Resources/Interview-Prep]]

## Ресурсы

1. System Design Interview by Alex Xu: https://www.amazon.com/System-Design-Interview-Insiders-Guide/dp/B08CMF2CQF
2. Designing Data-Intensive Applications by Martin Kleppmann: https://dataintensive.net/
3. DDIA Glossary: https://github.com/ept/ddia-references

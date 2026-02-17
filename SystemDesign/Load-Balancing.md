---
tags:
  - system-design
  - networking
  - load-balancing
created: 2026-02-17
---

# Балансировка нагрузки / Load Balancing

## Что это

Балансировка нагрузки — процесс распределения сетевого трафика между несколькими серверами для обеспечения высокой доступности и отзывчивости. Ключевые решения: L4 vs L7, выбор алгоритма, health checks.

---

## Introduction / Введение

Load balancing is the process of distributing network traffic across multiple servers to ensure no single server bears too much demand. This improves responsiveness and increases availability of applications.

Балансировка нагрузки — это процесс распределения сетевого трафика между несколькими серверами, чтобы ни один сервер не нес слишком большую нагрузку. Это улучшает отзывчивость и повышает доступность приложений.

```
                    ┌─────────────────┐
                    │   Load Balancer │
                    │   (балансировщик)│
                    └────────┬────────┘
                             │
           ┌─────────────────┼─────────────────┐
           │                 │                 │
           ▼                 ▼                 ▼
    ┌──────────┐      ┌──────────┐      ┌──────────┐
    │ Server 1 │      │ Server 2 │      │ Server 3 │
    │ (сервер) │      │ (сервер) │      │ (сервер) │
    └──────────┘      └──────────┘      └──────────┘
```

---

## L4 vs L7 Load Balancing / Балансировка L4 vs L7

### Layer 4 (Transport Layer) / Уровень 4 (Транспортный уровень)

L4 load balancers operate at the transport layer, making routing decisions based on IP addresses and TCP/UDP ports. They do not inspect the content of packets.

Балансировщики L4 работают на транспортном уровне, принимая решения о маршрутизации на основе IP-адресов и портов TCP/UDP. Они не проверяют содержимое пакетов.

**Characteristics / Характеристики:**
- Works with TCP/UDP connections / Работает с соединениями TCP/UDP
- Very fast (nanosecond latency) / Очень быстрый (задержка в наносекундах)
- Connection-based routing / Маршрутизация на основе соединений
- Cannot read HTTP headers or cookies / Не может читать HTTP-заголовки или куки

```
┌─────────────────────────────────────────────────────────────┐
│                    L4 Load Balancer                         │
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │ Source IP   │ +  │ Dest IP     │ +  │ Port Number │     │
│  │ (исх. IP)   │    │ (целевой IP)│    │ (номер порта)│    │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                           │                                 │
│                           ▼                                 │
│                  Routing Decision                           │
│                (решение о маршруте)                         │
└─────────────────────────────────────────────────────────────┘
```

**Use cases / Случаи использования:**
- High-throughput applications / Приложения с высокой пропускной способностью
- Non-HTTP protocols (databases, gaming) / Протоколы не-HTTP (базы данных, игры)
- Simple TCP/UDP services / Простые сервисы TCP/UDP

### Layer 7 (Application Layer) / Уровень 7 (Прикладной уровень)

L7 load balancers operate at the application layer, inspecting HTTP/HTTPS traffic content to make intelligent routing decisions.

Балансировщики L7 работают на прикладном уровне, проверяя содержимое трафика HTTP/HTTPS для принятия интеллектуальных решений о маршрутизации.

**Characteristics / Характеристики:**
- Content-aware routing / Маршрутизация с учетом содержимого
- Can inspect headers, cookies, URLs / Может проверять заголовки, куки, URL
- SSL/TLS termination / Терминация SSL/TLS
- Higher latency than L4 / Выше задержка, чем у L4

```
┌─────────────────────────────────────────────────────────────┐
│                    L7 Load Balancer                         │
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Headers  │ │ Cookies  │ │ URL Path │ │ Body     │       │
│  │(заголовки)│ │ (куки)   │ │ (путь)   │ │ (тело)   │       │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘       │
│       │            │            │            │              │
│       └────────────┴─────┬──────┴────────────┘              │
│                          ▼                                  │
│              Content-Based Routing                          │
│         (маршрутизация по содержимому)                      │
└─────────────────────────────────────────────────────────────┘
```

**Use cases / Случаи использования:**
- Microservices routing / Маршрутизация микросервисов
- A/B testing / A/B тестирование
- API gateways / API-шлюзы
- Session persistence / Сохранение сессий

---

## Load Balancing Algorithms / Алгоритмы балансировки

### 1. Round Robin / Циклический (Round Robin)

The simplest algorithm that distributes requests sequentially across all servers in rotation.

Простейший алгоритм, распределяющий запросы последовательно по всем серверам по кругу.

```
Request 1 → Server A
Request 2 → Server B
Request 3 → Server C
Request 4 → Server A  (cycle repeats / цикл повторяется)
Request 5 → Server B
...
```

**Pros / Преимущества:**
- Simple implementation / Простая реализация
- No state required / Не требуется состояние
- Equal distribution / Равное распределение

**Cons / Недостатки:**
- Ignores server capacity / Игнорирует мощность сервера
- Ignores current load / Игнорирует текущую нагрузку
- Not suitable for varying request complexity / Не подходит для запросов разной сложности

### 2. Weighted Round Robin / Взвешенный Round Robin

Extension of Round Robin where servers have different weights based on their capacity.

Расширение Round Robin, где серверы имеют разные веса в зависимости от их мощности.

```
Server A (weight=5): ■■■■■
Server B (weight=3): ■■■
Server C (weight=2): ■■

Distribution: A, A, A, A, A, B, B, B, C, C, (repeat)
```

### 3. Least Connections / Наименьшее количество соединений

Routes traffic to the server with the fewest active connections.

Направляет трафик на сервер с наименьшим количеством активных соединений.

```
┌────────────────────────────────────────────────────────────┐
│              Least Connections Algorithm                    │
│                                                            │
│  Server A: ████████████████ (16 connections)               │
│  Server B: ██████████ (10 connections)  ← New request here │
│  Server C: ████████████████████ (20 connections)           │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

**Pros / Преимущества:**
- Adapts to server load / Адаптируется к нагрузке сервера
- Good for long-lived connections / Хорош для долгих соединений
- Handles varying request times / Обрабатывает запросы разной длительности

**Cons / Недостатки:**
- Requires connection tracking / Требует отслеживания соединений
- More complex implementation / Более сложная реализация

### 4. Weighted Least Connections / Взвешенное наименьшее количество соединений

Combines least connections with server weights for capacity-aware distribution.

Комбинирует наименьшее количество соединений с весами серверов для распределения с учетом мощности.

```python
# Algorithm: Select server with lowest (active_connections / weight)
# Алгоритм: Выбрать сервер с наименьшим (активные_соединения / вес)

def select_server(servers):
    return min(servers, key=lambda s: s.connections / s.weight)
```

### 5. IP Hash / Хеширование IP

Uses client IP address hash to determine which server receives the request, ensuring session persistence.

Использует хеш IP-адреса клиента для определения сервера, обеспечивая сохранение сессии.

```
┌─────────────────────────────────────────────────────────────┐
│                    IP Hash Algorithm                        │
│                                                             │
│   Client IP: 192.168.1.100                                  │
│        │                                                    │
│        ▼                                                    │
│   hash("192.168.1.100") = 0x7A3B...                        │
│        │                                                    │
│        ▼                                                    │
│   0x7A3B... % 3 = 1  →  Server B                           │
│                                                             │
│   Same client always goes to same server                    │
│   (один клиент всегда идет на один сервер)                 │
└─────────────────────────────────────────────────────────────┘
```

**Pros / Преимущества:**
- Session persistence without cookies / Сохранение сессии без куки
- Stateless load balancer / Балансировщик без состояния
- Consistent routing / Согласованная маршрутизация

**Cons / Недостатки:**
- Uneven distribution with few clients / Неравное распределение при малом числе клиентов
- Server changes affect all sessions / Изменения серверов влияют на все сессии

### 6. Consistent Hashing / Консистентное хеширование

Advanced hash-based algorithm that minimizes redistribution when servers are added or removed.

Продвинутый алгоритм хеширования, минимизирующий перераспределение при добавлении или удалении серверов.

```
            ┌─────────────────────────────────┐
            │     Hash Ring (хеш-кольцо)      │
            │                                 │
            │        Server A                 │
            │           ●                     │
            │      ╱         ╲                │
            │    ╱             ╲              │
            │   ●               ●             │
            │ Server C      Server B          │
            │    ╲             ╱              │
            │      ╲         ╱                │
            │        ● ← Client request       │
            │      (goes to next server       │
            │       clockwise: Server B)      │
            └─────────────────────────────────┘
```

---

## Health Checks / Проверки состояния

Health checks ensure traffic is only sent to healthy servers.

Проверки состояния гарантируют, что трафик отправляется только на здоровые серверы.

### Types / Типы

| Type / Тип | Layer / Уровень | Method / Метод | Use Case / Применение |
|------------|-----------------|----------------|----------------------|
| TCP | L4 | Port connection | Basic availability / Базовая доступность |
| HTTP | L7 | GET /health | Web services / Веб-сервисы |
| Custom | L7 | Application logic | Complex checks / Сложные проверки |

```python
# Example health check endpoint / Пример эндпоинта проверки состояния
from fastapi import FastAPI
from datetime import datetime

app = FastAPI()

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "1.0.0",
        "checks": {
            "database": "ok",
            "cache": "ok",
            "disk_space": "ok"
        }
    }
```

---

## Implementation Examples / Примеры реализации

### NGINX L7 Load Balancer / Балансировщик NGINX L7

```nginx
# /etc/nginx/nginx.conf

upstream backend_servers {
    # Least connections with weights
    # Наименьшее количество соединений с весами
    least_conn;

    server backend1.example.com:8080 weight=5;
    server backend2.example.com:8080 weight=3;
    server backend3.example.com:8080 weight=2;

    # Health check configuration
    # Конфигурация проверки состояния
    keepalive 32;
}

server {
    listen 80;

    location / {
        proxy_pass http://backend_servers;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # Timeouts
        proxy_connect_timeout 5s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Content-based routing / Маршрутизация по содержимому
    location /api/v1/ {
        proxy_pass http://api_v1_servers;
    }

    location /api/v2/ {
        proxy_pass http://api_v2_servers;
    }
}
```

### HAProxy L4/L7 Configuration / Конфигурация HAProxy L4/L7

```haproxy
# /etc/haproxy/haproxy.cfg

global
    maxconn 50000
    log /dev/log local0

defaults
    mode http
    timeout connect 5s
    timeout client 30s
    timeout server 30s
    option httplog

# L4 Load Balancing for TCP services
# L4 балансировка для TCP-сервисов
frontend tcp_front
    mode tcp
    bind *:5432
    default_backend postgres_servers

backend postgres_servers
    mode tcp
    balance roundrobin
    server pg1 10.0.0.1:5432 check
    server pg2 10.0.0.2:5432 check

# L7 Load Balancing for HTTP
# L7 балансировка для HTTP
frontend http_front
    bind *:80
    bind *:443 ssl crt /etc/ssl/certs/cert.pem

    # ACL rules for routing / Правила ACL для маршрутизации
    acl is_api path_beg /api
    acl is_static path_beg /static

    use_backend api_servers if is_api
    use_backend static_servers if is_static
    default_backend web_servers

backend api_servers
    balance leastconn
    option httpchk GET /health
    http-check expect status 200
    server api1 10.0.1.1:8080 check weight 5
    server api2 10.0.1.2:8080 check weight 3

backend web_servers
    balance source  # IP Hash
    cookie SERVERID insert indirect nocache
    server web1 10.0.2.1:8080 check cookie s1
    server web2 10.0.2.2:8080 check cookie s2
```

---

## Comparison Table / Сравнительная таблица

| Feature / Особенность | L4 | L7 |
|----------------------|----|----|
| **Speed / Скорость** | Very fast / Очень быстрый | Fast / Быстрый |
| **Latency / Задержка** | ~1-10 us | ~100 us - 1 ms |
| **SSL Termination / SSL терминация** | No / Нет | Yes / Да |
| **Content Routing / Маршрутизация по содержимому** | No / Нет | Yes / Да |
| **Cookie Persistence / Сохранение по куки** | No / Нет | Yes / Да |
| **Complexity / Сложность** | Low / Низкая | High / Высокая |
| **Use Case / Применение** | TCP/UDP, DBs / БД | HTTP, APIs, Microservices |

| Algorithm / Алгоритм | Persistence / Сохранение | Load-Aware / Учет нагрузки | Complexity / Сложность |
|---------------------|-------------------------|---------------------------|------------------------|
| Round Robin | No / Нет | No / Нет | Simple / Простой |
| Weighted RR | No / Нет | Partial / Частично | Simple / Простой |
| Least Connections | No / Нет | Yes / Да | Medium / Средний |
| IP Hash | Yes / Да | No / Нет | Simple / Простой |
| Consistent Hash | Yes / Да | No / Нет | Complex / Сложный |

---

## Best Practices / Лучшие практики

1. **Use health checks aggressively** / **Используйте активные проверки состояния**
   - Check every 5-10 seconds / Проверяйте каждые 5-10 секунд
   - Remove unhealthy servers immediately / Немедленно удаляйте нездоровые серверы

2. **Choose the right layer** / **Выбирайте правильный уровень**
   - L4 for raw performance / L4 для максимальной производительности
   - L7 for content-aware routing / L7 для маршрутизации по содержимому

3. **Plan for failure** / **Планируйте отказы**
   - At least 2 load balancers / Минимум 2 балансировщика
   - Geographic distribution / Географическое распределение

4. **Monitor everything** / **Мониторьте все**
   - Connection counts / Количество соединений
   - Response times / Время отклика
   - Error rates / Частота ошибок

5. **Consider session persistence needs** / **Учитывайте требования к сохранению сессий**
   - Stateless apps: Any algorithm / Без состояния: любой алгоритм
   - Stateful apps: IP Hash or sticky sessions / С состоянием: IP Hash или липкие сессии

---

## Связано с

- [[DNS-CDN]]
- [[API-Gateway]]
- [[PV-Networking]]

## Ресурсы

1. NGINX Documentation - Load Balancing: https://nginx.org/en/docs/http/load_balancing.html
2. HAProxy Documentation: https://www.haproxy.org/documentation/
3. AWS Elastic Load Balancing: https://docs.aws.amazon.com/elasticloadbalancing/
4. Google Cloud Load Balancing: https://cloud.google.com/load-balancing/docs
5. "The Art of Scalability" - Martin L. Abbott, Michael T. Fisher
6. Cloudflare Learning Center - Load Balancing: https://www.cloudflare.com/learning/performance/what-is-load-balancing/

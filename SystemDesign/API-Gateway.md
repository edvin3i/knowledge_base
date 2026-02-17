---
tags:
  - system-design
  - networking
  - api-gateway
  - rate-limiting
created: 2026-02-17
---

# Паттерны API Gateway / API Gateway Patterns

## Что это

API Gateway — сервер, выступающий единой точкой входа для всех клиентских запросов. Обрабатывает аутентификацию, rate limiting, маршрутизацию, трансформацию запросов. Ключевые паттерны: BFF, Circuit Breaker, Token Bucket.

---

## Introduction / Введение

An API Gateway is a server that acts as a single entry point for all client requests. It handles cross-cutting concerns such as authentication, rate limiting, and request routing.

API Gateway — это сервер, который выступает единой точкой входа для всех клиентских запросов. Он обрабатывает сквозные задачи, такие как аутентификация, ограничение частоты запросов и маршрутизация.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    API Gateway Responsibilities                          │
│                 (Обязанности API Gateway)                                │
│                                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │ Routing     │  │ AuthN/AuthZ │  │ Rate Limit  │  │ Transform   │    │
│  │(маршрутизац)│  │(аутент/автор)│ │(огр.частоты)│  │(трансформац)│    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │
│                                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │ Load Balance│  │ Caching     │  │ Monitoring  │  │ Circuit Brkr│    │
│  │(балансировка)│ │(кеширование)│  │(мониторинг) │  │(размыкатель)│    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Gateway vs Service Mesh / Gateway vs Service Mesh

| Aspect / Аспект | API Gateway | Service Mesh |
|-----------------|-------------|--------------|
| Position / Позиция | Edge (north-south) | Internal (east-west) |
| Traffic / Трафик | External clients | Service-to-service |
| Protocols / Протоколы | HTTP/REST/GraphQL | gRPC, HTTP, TCP |
| Examples / Примеры | Kong, NGINX, Envoy | Istio, Linkerd, Consul |

---

## BFF Pattern / Паттерн BFF

The Backend for Frontend (BFF) pattern creates dedicated backend services for each frontend application type.

Паттерн Backend for Frontend (BFF) создает выделенные бэкенд-сервисы для каждого типа фронтенд-приложения.

### Problem / Проблема

```
┌─────────────────────────────────────────────────────────────────────────┐
│                Without BFF / Без BFF                                     │
│                                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                              │
│  │   Web    │  │  Mobile  │  │    TV    │                              │
│  │(веб-прил)│  │(мобильное)│ │    (ТВ)   │                              │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                              │
│       │             │             │                                     │
│       └─────────────┼─────────────┘                                     │
│                     │                                                   │
│                     ▼                                                   │
│            ┌────────────────┐                                          │
│            │ Generic API    │  ← Over-fetching / Избыточные данные     │
│            │ (общий API)    │  ← Under-fetching / Недостаток данных    │
│            └────────────────┘  ← Different needs / Разные потребности  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Solution / Решение

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   With BFF / С BFF                                       │
│                                                                         │
│  ┌──────────┐       ┌──────────┐       ┌──────────┐                    │
│  │   Web    │       │  Mobile  │       │    TV    │                    │
│  │(веб-прил)│       │(мобильное)│      │    (ТВ)   │                   │
│  └────┬─────┘       └────┬─────┘       └────┬─────┘                    │
│       │                  │                  │                          │
│       ▼                  ▼                  ▼                          │
│  ┌──────────┐       ┌──────────┐       ┌──────────┐                    │
│  │ Web BFF  │       │Mobile BFF│       │  TV BFF  │                    │
│  │(веб БФФ) │       │(моб БФФ) │       │ (ТВ БФФ) │                    │
│  └────┬─────┘       └────┬─────┘       └────┬─────┘                    │
│       │                  │                  │                          │
│       └──────────────────┼──────────────────┘                          │
│                          │                                             │
│            ┌─────────────┼─────────────┐                               │
│            │             │             │                               │
│            ▼             ▼             ▼                               │
│       ┌─────────┐   ┌─────────┐   ┌─────────┐                         │
│       │ Service │   │ Service │   │ Service │                         │
│       │    A    │   │    B    │   │    C    │                         │
│       └─────────┘   └─────────┘   └─────────┘                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### BFF Responsibilities / Обязанности BFF

1. **API Composition** / Композиция API
   - Aggregate multiple service calls / Агрегация нескольких вызовов сервисов
   - Reduce round trips / Уменьшение количества запросов

2. **Response Shaping** / Формирование ответа
   - Return only needed fields / Возврат только нужных полей
   - Format data for client needs / Форматирование данных под нужды клиента

3. **Protocol Translation** / Трансляция протоколов
   - REST to GraphQL / REST в GraphQL
   - gRPC to REST / gRPC в REST

```python
# BFF Example - Mobile-optimized endpoint
# Пример BFF - оптимизированный для мобильных эндпоинт

from fastapi import FastAPI, Depends
from pydantic import BaseModel
import httpx

app = FastAPI()

class MobileMatchSummary(BaseModel):
    """Optimized response for mobile / Оптимизированный ответ для мобильных"""
    match_id: str
    home_team: str
    away_team: str
    score: str
    thumbnail_url: str  # Low-res for mobile / Низкое разрешение для мобильных

@app.get("/mobile/matches/{match_id}", response_model=MobileMatchSummary)
async def get_mobile_match(match_id: str):
    """
    BFF endpoint that aggregates data from multiple services
    BFF-эндпоинт, агрегирующий данные из нескольких сервисов
    """
    async with httpx.AsyncClient() as client:
        # Parallel requests / Параллельные запросы
        match_task = client.get(f"http://catalog-service/matches/{match_id}")
        assets_task = client.get(f"http://catalog-service/matches/{match_id}/assets")

        match_resp, assets_resp = await asyncio.gather(match_task, assets_task)
        match_data = match_resp.json()
        assets_data = assets_resp.json()

    # Shape response for mobile / Формируем ответ для мобильных
    return MobileMatchSummary(
        match_id=match_id,
        home_team=match_data["home_team"]["name"],  # Flatten nested
        away_team=match_data["away_team"]["name"],
        score=f"{match_data['home_score']}-{match_data['away_score']}",
        thumbnail_url=assets_data["thumbnails"]["mobile"]  # Mobile-specific
    )
```

---

## Rate Limiting / Ограничение частоты запросов

Rate limiting protects APIs from abuse and ensures fair resource allocation.

Ограничение частоты запросов защищает API от злоупотреблений и обеспечивает справедливое распределение ресурсов.

### Algorithms / Алгоритмы

#### 1. Token Bucket / Корзина токенов

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Token Bucket Algorithm                              │
│                   (Алгоритм корзины токенов)                            │
│                                                                         │
│    ┌───────────────────────────────────────┐                           │
│    │  Bucket capacity: 10 tokens           │                           │
│    │  (вместимость: 10 токенов)            │                           │
│    │                                        │                           │
│    │  ●●●●●●●●○○  (8 tokens available)     │                           │
│    │                                        │                           │
│    └───────────────────────────────────────┘                           │
│              ↑                    ↓                                     │
│              │                    │                                     │
│    Refill: 1 token/second    Request consumes 1 token                  │
│    (пополнение: 1/сек)       (запрос потребляет 1 токен)               │
│                                                                         │
│    Properties / Свойства:                                               │
│    - Allows bursts up to bucket size / Разрешает всплески              │
│    - Smooth rate limiting / Плавное ограничение                        │
│    - Memory efficient / Эффективно по памяти                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 2. Sliding Window Log / Скользящее окно с логом

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Sliding Window Log                                    │
│                (Скользящее окно с логом)                                │
│                                                                         │
│  Time window: 60 seconds, Limit: 100 requests                          │
│  (окно: 60 секунд, лимит: 100 запросов)                                │
│                                                                         │
│  Timestamp log / Лог временных меток:                                   │
│  [12:00:05, 12:00:15, 12:00:23, 12:00:45, 12:00:58, ...]               │
│                                                                         │
│       │◀────────── 60 second window ──────────▶│                        │
│       │                                         │                        │
│  ─────┼───●─────●───────●───────────●───────●──┼──── Time               │
│    12:00:00                                 12:01:00                     │
│                                                                         │
│  Count requests in window / Подсчет запросов в окне                     │
│  Remove expired entries / Удаление устаревших записей                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 3. Sliding Window Counter / Скользящее окно со счетчиком

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   Sliding Window Counter                                 │
│                 (Скользящее окно со счетчиком)                          │
│                                                                         │
│  Previous window: 80 requests | Current window: 30 requests            │
│  (предыдущее: 80)             | (текущее: 30)                          │
│                                                                         │
│       │        │        │                                               │
│  ─────┼────────┼────────┼────── Time                                   │
│    12:00    12:01    12:02                                              │
│             │        │                                                  │
│             │◀─ 30s ─▶│  (30 seconds into current minute)               │
│                                                                         │
│  Weighted count / Взвешенный подсчет:                                   │
│  = prev_count × (1 - elapsed/window) + curr_count                       │
│  = 80 × (1 - 30/60) + 30 = 80 × 0.5 + 30 = 70 requests                 │
│                                                                         │
│  Memory efficient: O(1) / Эффективно по памяти: O(1)                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Rate Limit Implementation / Реализация ограничения частоты

```python
# Redis-based Token Bucket implementation
# Реализация корзины токенов на Redis

import redis
import time
from fastapi import FastAPI, HTTPException, Request

app = FastAPI()
redis_client = redis.Redis(host='redis-cache', port=6379)

class TokenBucket:
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate  # tokens per second

    def is_allowed(self, key: str, tokens: int = 1) -> tuple[bool, dict]:
        """
        Check if request is allowed and consume tokens
        Проверить разрешен ли запрос и потребить токены
        """
        now = time.time()

        # Lua script for atomic operation
        # Lua скрипт для атомарной операции
        lua_script = """
        local key = KEYS[1]
        local capacity = tonumber(ARGV[1])
        local refill_rate = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local requested = tonumber(ARGV[4])

        local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
        local tokens = tonumber(bucket[1]) or capacity
        local last_refill = tonumber(bucket[2]) or now

        -- Refill tokens / Пополнение токенов
        local elapsed = now - last_refill
        local refill = elapsed * refill_rate
        tokens = math.min(capacity, tokens + refill)

        local allowed = tokens >= requested
        if allowed then
            tokens = tokens - requested
        end

        redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
        redis.call('EXPIRE', key, 3600)

        return {allowed and 1 or 0, tokens, capacity}
        """

        result = redis_client.eval(
            lua_script, 1, key,
            self.capacity, self.refill_rate, now, tokens
        )

        allowed = bool(result[0])
        remaining = int(result[1])
        limit = int(result[2])

        return allowed, {
            "X-RateLimit-Remaining": remaining,
            "X-RateLimit-Limit": limit,
            "X-RateLimit-Reset": int(now + (self.capacity - remaining) / self.refill_rate)
        }

# Rate limiter instances / Экземпляры ограничителей
default_limiter = TokenBucket(capacity=100, refill_rate=10)  # 100 tokens, 10/sec refill
premium_limiter = TokenBucket(capacity=1000, refill_rate=100)

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Get client identifier / Получаем идентификатор клиента
    client_id = request.headers.get("X-API-Key", request.client.host)

    # Check rate limit / Проверяем ограничение
    allowed, headers = default_limiter.is_allowed(f"ratelimit:{client_id}")

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too Many Requests / Слишком много запросов",
            headers=headers
        )

    response = await call_next(request)

    # Add rate limit headers / Добавляем заголовки ограничения
    for key, value in headers.items():
        response.headers[key] = str(value)

    return response
```

---

## Circuit Breaker / Размыкатель цепи

The Circuit Breaker pattern prevents cascading failures by failing fast when a service is unhealthy.

Паттерн размыкателя цепи предотвращает каскадные отказы, быстро отказывая при нездоровом сервисе.

### State Machine / Состояния

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Circuit Breaker States                                │
│                (Состояния размыкателя цепи)                             │
│                                                                         │
│                        ┌──────────────┐                                 │
│              ┌────────>│    CLOSED    │<────────┐                       │
│              │         │  (закрыт)    │         │                       │
│              │         └──────┬───────┘         │                       │
│              │                │                 │                       │
│              │    Failure threshold reached     │                       │
│              │    (достигнут порог ошибок)     │                       │
│              │                │                 │                       │
│              │                ▼                 │                       │
│    Success   │         ┌──────────────┐         │  Success below        │
│   threshold  │         │     OPEN     │         │  threshold            │
│   reached    │         │   (открыт)   │         │  (успех ниже порога)  │
│              │         └──────┬───────┘         │                       │
│              │                │                 │                       │
│              │    Timeout expires               │                       │
│              │    (таймаут истек)               │                       │
│              │                │                 │                       │
│              │                ▼                 │                       │
│              │         ┌──────────────┐         │                       │
│              └─────────│  HALF-OPEN   │─────────┘                       │
│                        │(полуоткрыт)  │                                 │
│                        └──────────────┘                                 │
│                                                                         │
│  CLOSED: All requests pass / Все запросы проходят                      │
│  OPEN: All requests fail fast / Все запросы быстро отказывают          │
│  HALF-OPEN: Limited requests to test / Ограниченные запросы для теста  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Implementation / Реализация

```python
# Circuit Breaker implementation
# Реализация размыкателя цепи

import asyncio
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
import httpx

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    success_threshold: int = 3
    timeout_duration: timedelta = timedelta(seconds=30)
    half_open_max_calls: int = 3

class CircuitBreaker:
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.half_open_calls = 0

    async def call(self, func, *args, **kwargs):
        """
        Execute function with circuit breaker protection
        Выполнить функцию с защитой размыкателем
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
            else:
                raise CircuitBreakerOpen(
                    f"Circuit breaker {self.name} is OPEN / "
                    f"Размыкатель {self.name} ОТКРЫТ"
                )

        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.config.half_open_max_calls:
                raise CircuitBreakerOpen(
                    f"Circuit breaker {self.name} half-open limit reached / "
                    f"Достигнут лимит полуоткрытого состояния"
                )
            self.half_open_calls += 1

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        """Handle successful call / Обработать успешный вызов"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self._reset()
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def _on_failure(self):
        """Handle failed call / Обработать неудачный вызов"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
            self.success_count = 0

    def _should_attempt_reset(self) -> bool:
        """Check if timeout has passed / Проверить истек ли таймаут"""
        if not self.last_failure_time:
            return True
        return datetime.utcnow() - self.last_failure_time > self.config.timeout_duration

    def _reset(self):
        """Reset to closed state / Сброс в закрытое состояние"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0

class CircuitBreakerOpen(Exception):
    pass

# Usage example / Пример использования
catalog_circuit = CircuitBreaker(
    name="catalog-service",
    config=CircuitBreakerConfig(
        failure_threshold=5,
        timeout_duration=timedelta(seconds=30)
    )
)

async def get_match_with_circuit_breaker(match_id: str):
    async def fetch_match():
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://catalog-service:8003/matches/{match_id}",
                timeout=5.0
            )
            response.raise_for_status()
            return response.json()

    try:
        return await catalog_circuit.call(fetch_match)
    except CircuitBreakerOpen:
        # Return cached/default response
        # Вернуть кешированный/дефолтный ответ
        return get_cached_match(match_id)
```

---

## Authentication and Authorization / Аутентификация и авторизация

### JWT Validation at Gateway / Валидация JWT на шлюзе

```python
# JWT validation middleware
# Middleware для валидации JWT

from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime

app = FastAPI()
security = HTTPBearer()

JWT_SECRET = "your-secret-key"  # In production: from vault/env
JWT_ALGORITHM = "HS256"

async def validate_token(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> dict:
    """
    Validate JWT token at gateway level
    Валидация JWT токена на уровне шлюза
    """
    token = credentials.credentials

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

        # Check expiration / Проверка срока действия
        if datetime.utcnow().timestamp() > payload.get("exp", 0):
            raise HTTPException(status_code=401, detail="Token expired")

        return payload

    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token: {str(e)}"
        )

async def require_role(required_roles: list[str]):
    """
    Role-based access control decorator
    Декоратор контроля доступа на основе ролей
    """
    async def role_checker(user: dict = Depends(validate_token)):
        user_roles = user.get("roles", [])
        if not any(role in user_roles for role in required_roles):
            raise HTTPException(
                status_code=403,
                detail=f"Requires one of roles: {required_roles}"
            )
        return user
    return role_checker

# Protected endpoint example
# Пример защищенного эндпоинта
@app.get("/admin/matches")
async def admin_matches(user: dict = Depends(require_role(["admin", "staff"]))):
    return {"user": user["sub"], "matches": [...]}
```

---

## Request Transformation / Трансформация запросов

```python
# Request/Response transformation
# Трансформация запросов и ответов

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import json

class TransformMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Transform incoming request / Трансформация входящего запроса
        if request.headers.get("X-API-Version") == "1":
            request = await self._transform_v1_to_v2(request)

        response = await call_next(request)

        # Transform outgoing response / Трансформация исходящего ответа
        if request.headers.get("Accept-Encoding-Custom") == "compact":
            response = await self._compact_response(response)

        return response

    async def _transform_v1_to_v2(self, request: Request) -> Request:
        """Transform v1 API request to v2 format"""
        # Implementation / Реализация
        return request

    async def _compact_response(self, response: Response) -> Response:
        """Remove null fields from JSON response"""
        # Implementation / Реализация
        return response
```

---

## Comparison Table / Сравнительная таблица

### API Gateway Solutions / Решения API Gateway

| Solution / Решение | Type / Тип | Best For / Лучше для | Language / Язык | Routing / Маршрутизация |
|-------------------|-----------|---------------------|-----------------|------------------------|
| **Apache APISIX** | Self-hosted | **Multi-lang plugins, high perf** | Lua/Python/Go/Java/WASM | **O(k) radix tree** |
| Kong | Self-hosted/Cloud | Kubernetes, plugins | Lua only | O(n) linear |
| AWS API Gateway | Cloud | AWS ecosystem | N/A | Managed |
| NGINX Plus | Self-hosted | High performance | Config | Trie-based |
| Traefik | Self-hosted | Docker/K8s native | Go | Label-based |
| Express Gateway | Self-hosted | Node.js apps | JavaScript | O(n) |
| FastAPI (custom) | Self-hosted | Simple Python apps | Python | O(n) dict |

### Rate Limiting Algorithms / Алгоритмы ограничения частоты

| Algorithm / Алгоритм | Memory / Память | Accuracy / Точность | Burst Handling / Всплески |
|---------------------|-----------------|--------------------|-----------------------------|
| Fixed Window | O(1) | Low / Низкая | Poor / Плохо |
| Sliding Log | O(n) | High / Высокая | Good / Хорошо |
| Sliding Counter | O(1) | Medium / Средняя | Good / Хорошо |
| Token Bucket | O(1) | High / Высокая | Excellent / Отлично |
| Leaky Bucket | O(1) | High / Высокая | Smooth / Плавно |

---

## Связано с

- [[Load-Balancing]]
- [[DNS-CDN]]
- [[PV-Networking]]
- [[Authentication]]
- [[Authorization]]

## Ресурсы

1. Microsoft - API Gateway pattern: https://docs.microsoft.com/en-us/azure/architecture/microservices/design/gateway
2. Netflix - Zuul Gateway: https://github.com/Netflix/zuul
3. Martin Fowler - Circuit Breaker: https://martinfowler.com/bliki/CircuitBreaker.html
4. Sam Newman - BFF Pattern: https://samnewman.io/patterns/architectural/bff/
5. Kong Documentation: https://docs.konghq.com/
6. AWS API Gateway: https://docs.aws.amazon.com/apigateway/
7. "Release It!" - Michael T. Nygard
8. "Building Microservices" - Sam Newman

---
tags:
  - polyvision
  - system-design
  - networking
  - apisix
created: 2026-02-17
---

# Polyvision: Сетевая архитектура / Gateway & Delivery

## Что это

Сетевой уровень Polyvision: Gateway/BFF (порт 8000) для API-маршрутизации и авторизации, Delivery Service (порт 8006) для HLS/DASH видеостриминга. Выбран Apache APISIX (ADR-023) вместо Kong/Traefik/кастомного FastAPI. Принцип "Process Once, Serve Many".

---

## Overview / Обзор

Polyvision's network layer follows the "Process Once, Serve Many" principle, handling video delivery to thousands of concurrent viewers while maintaining strict access control and optimal performance.

Сетевой уровень Polyvision следует принципу "Обработай один раз, обслуживай многих", обеспечивая доставку видео тысячам одновременных зрителей при строгом контроле доступа и оптимальной производительности.

### Key Requirements / Ключевые требования

| Requirement / Требование | Target / Цель |
|------------------------|---------------|
| Concurrent viewers / Одновременных зрителей | 10,000+ |
| Video latency (VOD) / Задержка видео (VOD) | < 2s initial buffer |
| Video latency (Live) / Задержка видео (Live) | < 8s end-to-end |
| API response time / Время ответа API | P99 < 200ms |
| Availability / Доступность | 99.9% |

---

## Architecture Decision / Архитектурное решение

### Why Separate Gateway and Delivery? / Почему отдельные шлюз и доставка?

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Polyvision Network Architecture                      │
│                  (Сетевая архитектура Polyvision)                       │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                        CDN Layer                                 │   │
│  │                      (Уровень CDN)                               │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐            │   │
│  │  │  PoP   │  │  PoP   │  │  PoP   │  │  PoP   │            │   │
│  │  │ Europe  │  │  Asia   │  │   US    │  │ Russia  │            │   │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘            │   │
│  └───────┼────────────┼────────────┼────────────┼──────────────────┘   │
│          │            │            │            │                       │
│          └────────────┴─────┬──────┴────────────┘                       │
│                             │                                           │
│  ┌──────────────────────────┴──────────────────────────┐               │
│  │                   Load Balancer                      │               │
│  │                 (Балансировщик L7)                   │               │
│  └───────────────┬───────────────────┬─────────────────┘               │
│                  │                   │                                  │
│     ┌────────────┴────┐    ┌────────┴──────────┐                       │
│     │                 │    │                   │                       │
│     ▼                 │    ▼                   │                       │
│  ┌────────────────┐   │  ┌────────────────┐    │                       │
│  │ Gateway/BFF    │   │  │ Delivery Svc   │    │                       │
│  │  (port 8000)   │   │  │  (port 8006)   │    │                       │
│  │                │   │  │                │    │                       │
│  │ - Routing      │   │  │ - HLS/DASH     │    │                       │
│  │ - AuthZ        │   │  │ - Signed URLs  │    │                       │
│  │ - Rate Limit   │   │  │ - CDN integ    │    │                       │
│  │ - Presigned    │   │  │ - Manifests    │    │                       │
│  └───────┬────────┘   │  └───────┬────────┘    │                       │
│          │            │          │             │                       │
│          ▼            │          ▼             │                       │
│  ┌─────────────────┐  │  ┌─────────────────┐   │                       │
│  │ Internal APIs   │  │  │ Object Storage  │   │                       │
│  │ Auth, Catalog,  │  │  │ MinIO/Ceph      │   │                       │
│  │ Processing...   │  │  │ (video assets)  │   │                       │
│  └─────────────────┘  │  └─────────────────┘   │                       │
│                       │                        │                       │
└───────────────────────┴────────────────────────┴───────────────────────┘
```

### Decision Rationale / Обоснование решения

| Aspect / Аспект | Gateway (8000) | Delivery (8006) |
|----------------|----------------|-----------------|
| **Traffic type** | API requests | Video streaming |
| **Request size** | Small (KB) | Large (MB-GB) |
| **Caching** | Short TTL | Long TTL |
| **Scaling** | CPU-bound | IO-bound |
| **Rate limiting** | Per-user/API | Per-stream/bandwidth |

**Separation benefits / Преимущества разделения:**
1. Independent scaling / Независимое масштабирование
2. Different optimization strategies / Разные стратегии оптимизации
3. Clearer security boundaries / Четкие границы безопасности
4. Easier troubleshooting / Упрощенная отладка

---

## Gateway Technology: Apache APISIX (ADR-023)

### Why Not Custom FastAPI Gateway? / Почему не кастомный FastAPI шлюз?

Initial proposal was a thin FastAPI reverse proxy (~200 lines). This was rejected because:

Первоначальное предложение — тонкий FastAPI обратный прокси (~200 строк). Отклонено потому что:

1. **Scale / Масштаб:** Polyvision has 8+ services, not 3. Building for "current needs only" is short-sighted when laying foundation for a distributed platform.
2. **Reinventing the wheel / Изобретение велосипеда:** Rate limiting, circuit breaker, health checks, metrics — all need reimplementation.
3. **No hot reload / Нет горячей перезагрузки:** Route changes require service restart.

### Gateway Comparison (2026) / Сравнение шлюзов (2026)

| Criteria / Критерий | Custom FastAPI | Traefik | Kong OSS | Apache APISIX |
|---------------------|----------------|---------|----------|---------------|
| **Routing** | O(n) dict lookup | Automatic (labels) | O(n) database | **O(k) radix tree** |
| **Performance (with plugins)** | Depends | N/A | ~3k RPS | **~30k RPS** |
| **JWT validation** | Custom code | Basic | Lua plugin | **Python/Lua/Go plugin** |
| **Rate limiting** | Custom Redis | Basic | Lua plugin | Redis-backed distributed |
| **Plugin language** | Python | Go | **Lua only** | **Lua, Python, Go, Java, WASM** |
| **Config management** | Code changes | Labels/files | Admin API + DB | Admin API + etcd / YAML |
| **Hot reload** | No (restart) | Yes (labels) | DB poll | **<1ms (etcd watch)** |
| **OSS health** | N/A | Active | **OSS/Enterprise split** | **Fully open (Apache Foundation)** |
| **K8s integration** | Manual | Built-in Ingress | KIC | APISIX Ingress Controller |

### Why APISIX Won / Почему победил APISIX

1. **Python plugins / Python-плагины** — Custom JWT validator (RS256 + EdDSA dual-algorithm) can be written in Python, reusing same PyJWT + cryptography stack as Auth/Device services.

2. **Performance with plugins / Производительность с плагинами** — APISIX uses radix tree for O(k) routing (k = URI length), while Kong uses O(n) traversal. With JWT + rate limiting enabled on every route, this becomes critical at 8+ services.

3. **No vendor lock-in / Нет привязки к вендору** — Apache Foundation project, fully open source. Kong OSS has diverged from Enterprise since v3.9.

4. **Deployment flexibility / Гибкость развёртывания:**
   - **Dev:** Standalone YAML (no etcd, like Kong DB-less)
   - **Stage:** Standalone -> single etcd when hot reload needed
   - **Prod:** Dedicated etcd cluster (3 replicas), isolated from K8s etcd

### etcd Isolation / Изоляция etcd

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    etcd Isolation Policy                                 │
│                 (Политика изоляции etcd)                                │
│                                                                         │
│  K3s Embedded etcd          ≠          APISIX etcd                     │
│  (Встроенный etcd K3s)                (etcd APISIX)                    │
│                                                                         │
│  - Stores K8s secrets                 - Stores routes, plugins          │
│  - localhost only                     - Internal network                │
│  - Managed by K3s lifecycle           - Managed independently          │
│  - Contains all cluster state         - Contains APISIX config only    │
│                                                                         │
│  WHY SEPARATE / ПОЧЕМУ ОТДЕЛЬНО:                                       │
│  1. Security: K8s secrets in same etcd = attack surface                │
│  2. Blast radius: APISIX bug → K8s instability                        │
│  3. Lifecycle: K3s upgrade could break APISIX config                   │
│  4. etcd is lightweight: ~50MB RAM per instance                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Interview Questions / Вопросы для интервью

**Q: Why not use Traefik since it's already deployed in your K3s cluster?**
A: Traefik handles L7 ingress (TLS termination, host-based routing) but doesn't support custom JWT claim validation. Our dual-algorithm JWT strategy (RS256 for users, EdDSA for devices) requires peeking at the `alg` header and selecting the correct key — this needs a programmable plugin, not just header forwarding.

**Q: Why is Kong not suitable despite being more popular?**
A: Three issues: (1) Lua-only plugins force us to rewrite JWT logic outside our Python stack, (2) O(n) route matching degrades with 8+ services, (3) OSS/Enterprise divergence since v3.9 means features may become Enterprise-only.

**Q: How do you handle the etcd operational overhead?**
A: Phased approach — Standalone YAML in dev (zero overhead), single etcd in staging, 3-node etcd in prod. etcd is battle-tested (Kubernetes runs on it), lightweight (~50MB RAM), and we isolate it from K8s etcd for security.

**Q: What happens if APISIX goes down?**
A: APISIX is stateless data plane — routing config is loaded from etcd (or YAML in Standalone). Multiple replicas behind a load balancer provide HA. If one pod crashes, others continue serving. Config survives restarts because it's stored externally.

---

## Gateway/BFF Service (Port 8000) / Шлюз/BFF сервис (порт 8000)

### Responsibilities / Обязанности

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Gateway Request Flow                                │
│                   (Поток запросов через шлюз)                           │
│                                                                         │
│  Client Request                                                         │
│       │                                                                 │
│       ▼                                                                 │
│  ┌─────────────┐                                                       │
│  │ Rate Limit  │──→ 429 Too Many Requests                              │
│  │(огр.частоты)│                                                       │
│  └──────┬──────┘                                                       │
│         │ ✓                                                             │
│         ▼                                                               │
│  ┌─────────────┐                                                       │
│  │ AuthN/AuthZ │──→ 401/403 Unauthorized                               │
│  │(аутент/автор)│                                                      │
│  └──────┬──────┘                                                       │
│         │ ✓                                                             │
│         ▼                                                               │
│  ┌─────────────┐                                                       │
│  │ Route Match │                                                       │
│  │(маршрутизац)│                                                       │
│  └──────┬──────┘                                                       │
│         │                                                               │
│    ┌────┴────┐                                                         │
│    │         │                                                         │
│    ▼         ▼                                                         │
│ /api/*    /stream/*                                                    │
│    │         │                                                         │
│    ▼         ▼                                                         │
│ Internal   Generate                                                    │
│ Services   Presigned URL                                               │
│    │       → Delivery                                                  │
│    │         Service                                                   │
│    ▼         │                                                         │
│ Response     ▼                                                         │
│           Redirect to                                                   │
│           CDN/Delivery                                                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Presigned URL Generation / Генерация подписанных URL

```python
# Gateway service - Presigned URL generation
# Сервис шлюза - Генерация подписанных URL

from fastapi import FastAPI, Depends, HTTPException
from datetime import datetime, timedelta
import hmac
import hashlib
import base64
from urllib.parse import urlencode

app = FastAPI()

class PresignedURLGenerator:
    def __init__(self, secret_key: str, delivery_base_url: str):
        self.secret_key = secret_key.encode()
        self.delivery_base_url = delivery_base_url

    def generate(
        self,
        resource_path: str,
        user_id: str,
        expires_in: timedelta = timedelta(hours=4),
        allowed_ips: list[str] = None
    ) -> str:
        """
        Generate a signed URL for video access
        Генерация подписанного URL для доступа к видео
        """
        expires = int((datetime.utcnow() + expires_in).timestamp())

        # Build signature payload / Формируем payload для подписи
        payload = {
            "path": resource_path,
            "user": user_id,
            "exp": expires,
        }

        if allowed_ips:
            payload["ips"] = ",".join(allowed_ips)

        # Create signature / Создаем подпись
        message = f"{resource_path}:{user_id}:{expires}"
        signature = hmac.new(
            self.secret_key,
            message.encode(),
            hashlib.sha256
        ).digest()

        sig_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")

        # Build final URL / Формируем итоговый URL
        params = {
            "u": user_id,
            "exp": expires,
            "sig": sig_b64
        }

        if allowed_ips:
            params["ips"] = ",".join(allowed_ips)

        return f"{self.delivery_base_url}{resource_path}?{urlencode(params)}"

url_generator = PresignedURLGenerator(
    secret_key="your-256-bit-secret",
    delivery_base_url="https://delivery.polyvision.io"
)

@app.get("/api/v1/matches/{match_id}/stream")
async def get_stream_url(
    match_id: str,
    quality: str = "auto",
    user: dict = Depends(validate_token_and_entitlements)
):
    """
    Generate presigned streaming URL for authorized user
    Генерация подписанного URL для авторизованного пользователя
    """
    # Check entitlements / Проверка прав доступа
    if not user_has_access(user, match_id):
        raise HTTPException(status_code=403, detail="No access to this match")

    # Generate different URLs based on quality preference
    manifest_path = f"/hls/{match_id}/master.m3u8"

    if quality != "auto":
        manifest_path = f"/hls/{match_id}/{quality}.m3u8"

    presigned_url = url_generator.generate(
        resource_path=manifest_path,
        user_id=user["sub"],
        expires_in=timedelta(hours=4),
        allowed_ips=[user.get("ip")] if user.get("restrict_ip") else None
    )

    return {
        "stream_url": presigned_url,
        "expires_at": (datetime.utcnow() + timedelta(hours=4)).isoformat() + "Z",
        "quality": quality,
        "player_config": {
            "type": "hls",
            "autoplay": True,
            "analytics_endpoint": "/api/v1/analytics/playback"
        }
    }
```

### Route Configuration / Конфигурация маршрутов

```python
# Gateway routing configuration
# Конфигурация маршрутизации шлюза

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
import httpx

ROUTE_CONFIG = {
    "/api/v1/auth": {"service": "auth-service", "port": 8001},
    "/api/v1/ingest": {"service": "ingestion-service", "port": 8002},
    "/api/v1/matches": {"service": "catalog-service", "port": 8003},
    "/api/v1/teams": {"service": "catalog-service", "port": 8003},
    "/api/v1/processing": {"service": "processing-orchestrator", "port": 8004},
    "/api/v1/analytics": {"service": "analytics-api", "port": 8005},
    "/api/v1/stream": {"handler": "presigned_url"},  # Handled locally
}
```

---

## Delivery Service (Port 8006) / Сервис доставки (порт 8006)

### Responsibilities / Обязанности

1. **Manifest generation** / Генерация манифестов HLS/DASH
2. **Signed URL validation** / Валидация подписанных URL
3. **CDN cache integration** / Интеграция с кешем CDN
4. **Adaptive bitrate control** / Контроль адаптивного битрейта

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   Delivery Service Architecture                          │
│                (Архитектура сервиса доставки)                           │
│                                                                         │
│  CDN Request                                                            │
│       │                                                                 │
│       ▼                                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Delivery Service (8006)                       │   │
│  │                                                                  │   │
│  │  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐        │   │
│  │  │   Signature  │   │   Manifest   │   │   Segment    │        │   │
│  │  │  Validator   │   │  Generator   │   │   Proxy      │        │   │
│  │  │(валидатор)   │   │(генератор)   │   │  (прокси)    │        │   │
│  │  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘        │   │
│  │         │                  │                  │                 │   │
│  │         ▼                  ▼                  ▼                 │   │
│  │  ┌─────────────────────────────────────────────────────────┐   │   │
│  │  │                  Object Storage Client                   │   │   │
│  │  │                    (MinIO/Ceph)                          │   │   │
│  │  └─────────────────────────────────────────────────────────┘   │   │
│  │                                                                  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Cache Headers Returned / Возвращаемые заголовки кеширования:          │
│  - Manifests: Cache-Control: public, max-age=2                         │
│  - Segments: Cache-Control: public, max-age=604800, immutable          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### HLS Manifest Generation / Генерация HLS манифестов

```python
# Delivery service - Dynamic manifest generation
# Сервис доставки - Динамическая генерация манифестов

from fastapi import FastAPI, HTTPException, Query, Response
from datetime import datetime
import hmac
import hashlib
import base64

app = FastAPI()

class SignatureValidator:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key.encode()

    def validate(self, path, user_id, expires, signature, client_ip=None, allowed_ips=None):
        """Validate presigned URL signature / Валидация подписи URL"""
        if datetime.utcnow().timestamp() > expires:
            return False
        if allowed_ips:
            ip_list = allowed_ips.split(",")
            if client_ip not in ip_list:
                return False
        message = f"{path}:{user_id}:{expires}"
        expected_sig = hmac.new(self.secret_key, message.encode(), hashlib.sha256).digest()
        expected_b64 = base64.urlsafe_b64encode(expected_sig).decode().rstrip("=")
        return hmac.compare_digest(signature, expected_b64)

def generate_master_manifest(match_id, renditions, user_id, expires, signature):
    """Generate HLS master manifest with multiple quality levels"""
    lines = ["#EXTM3U", "#EXT-X-VERSION:6"]
    profiles = [
        {"name": "1080p", "bandwidth": 5000000, "resolution": "1920x1080"},
        {"name": "720p", "bandwidth": 2500000, "resolution": "1280x720"},
        {"name": "480p", "bandwidth": 1000000, "resolution": "854x480"},
        {"name": "360p", "bandwidth": 500000, "resolution": "640x360"},
    ]
    for profile in profiles:
        if profile["name"] in renditions:
            variant_url = f"{profile['name']}.m3u8?u={user_id}&exp={expires}&sig={signature}"
            lines.append(
                f'#EXT-X-STREAM-INF:BANDWIDTH={profile["bandwidth"]},'
                f'RESOLUTION={profile["resolution"]},'
                f'CODECS="avc1.640028,mp4a.40.2"'
            )
            lines.append(variant_url)
    return "\n".join(lines)
```

---

## Rate Limiting Strategy / Стратегия ограничения частоты

### Multi-Tier Rate Limiting / Многоуровневое ограничение

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Rate Limiting Tiers                                   │
│              (Уровни ограничения частоты)                               │
│                                                                         │
│  Tier 1: Global Rate Limit / Глобальный лимит                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  100,000 requests/second across all services                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Tier 2: Per-Organization / По организации                             │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Free tier: 1,000 req/min     │  Premium: 10,000 req/min        │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Tier 3: Per-User / По пользователю                                    │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Viewer: 100 req/min  │  Staff: 500 req/min  │  Admin: 2000/min │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Tier 4: Per-Endpoint / По эндпоинту                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  /api/v1/auth/login: 5 req/min (brute force protection)         │   │
│  │  /api/v1/upload: 10 req/hour                                    │   │
│  │  /api/v1/matches: 60 req/min                                    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Rate Limit Configuration / Конфигурация ограничений

```python
from dataclasses import dataclass
from enum import Enum

class UserRole(Enum):
    VIEWER = "viewer"
    STAFF = "staff"
    ADMIN = "admin"
    OWNER = "owner"

class SubscriptionTier(Enum):
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"

@dataclass
class RateLimitConfig:
    requests_per_minute: int
    burst_size: int
    concurrent_streams: int

ROLE_LIMITS = {
    UserRole.VIEWER: RateLimitConfig(requests_per_minute=100, burst_size=20, concurrent_streams=2),
    UserRole.STAFF: RateLimitConfig(requests_per_minute=500, burst_size=100, concurrent_streams=5),
    UserRole.ADMIN: RateLimitConfig(requests_per_minute=2000, burst_size=500, concurrent_streams=10),
}

ORG_LIMITS = {
    SubscriptionTier.FREE: RateLimitConfig(requests_per_minute=1000, burst_size=200, concurrent_streams=10),
    SubscriptionTier.PREMIUM: RateLimitConfig(requests_per_minute=10000, burst_size=2000, concurrent_streams=100),
    SubscriptionTier.ENTERPRISE: RateLimitConfig(requests_per_minute=100000, burst_size=20000, concurrent_streams=1000),
}

ENDPOINT_LIMITS = {
    "/api/v1/auth/login": {"requests": 5, "window": 60},
    "/api/v1/auth/register": {"requests": 3, "window": 3600},
    "/api/v1/ingest/upload": {"requests": 10, "window": 3600},
    "/api/v1/processing/start": {"requests": 20, "window": 3600},
}
```

---

## Video Streaming Optimization / Оптимизация видеостриминга

### CDN Integration Strategy / Стратегия интеграции с CDN

```
┌─────────────────────────────────────────────────────────────────────────┐
│              Video Streaming Optimization Layers                         │
│           (Уровни оптимизации видеостриминга)                           │
│                                                                         │
│  Layer 1: CDN Edge Caching / Кеширование на краю CDN                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  - Video segments: 7 days TTL, immutable                         │   │
│  │  - Manifests: 2-5 seconds TTL (dynamic)                          │   │
│  │  - Thumbnails: 30 days TTL                                       │   │
│  │  - Expected cache hit rate: >95%                                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Layer 2: Regional Shield / Региональный щит                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  - 3 regional shields: EU (Frankfurt), US (Virginia), Asia (TKY)│   │
│  │  - Reduces origin load by 90%                                    │   │
│  │  - Handles cache misses from edge PoPs                           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Layer 3: Origin Protection / Защита источника                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  - Delivery Service only accepts CDN IPs                         │   │
│  │  - Request collapsing for simultaneous requests                  │   │
│  │  - MinIO direct read with connection pooling                     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Security Considerations / Соображения безопасности

| Layer / Уровень | Protection / Защита |
|----------------|---------------------|
| CDN | DDoS protection, WAF rules |
| Load Balancer | TLS termination, IP filtering |
| Gateway | Rate limiting, AuthN/AuthZ |
| Delivery | Signed URLs, IP restrictions |
| Origin | VPC isolation, mTLS |

---

## Monitoring and Observability / Мониторинг и наблюдаемость

### Key Metrics / Ключевые метрики

```python
from prometheus_client import Counter, Histogram, Gauge

# Gateway metrics
gateway_requests = Counter('gateway_requests_total', 'Total gateway requests', ['method', 'endpoint', 'status'])
gateway_latency = Histogram('gateway_request_duration_seconds', 'Request latency', ['endpoint'],
    buckets=[.01, .025, .05, .1, .25, .5, 1, 2.5, 5])
rate_limit_hits = Counter('rate_limit_hits_total', 'Rate limit triggered', ['tier', 'organization_id'])

# Delivery metrics
manifest_requests = Counter('delivery_manifest_requests_total', 'Manifest requests', ['match_id', 'quality'])
cdn_cache_status = Counter('cdn_cache_status_total', 'CDN cache hit/miss', ['status'])
active_streams = Gauge('active_streams', 'Currently active video streams', ['organization_id', 'quality'])
segment_bandwidth = Counter('segment_bandwidth_bytes_total', 'Total bandwidth served', ['quality'])
```

### Alert Rules / Правила алертов

```yaml
groups:
  - name: polyvision-gateway
    rules:
      - alert: HighRateLimitRate
        expr: rate(rate_limit_hits_total[5m]) > 100
        for: 2m
        labels:
          severity: warning
      - alert: GatewayLatencyHigh
        expr: histogram_quantile(0.99, rate(gateway_request_duration_seconds_bucket[5m])) > 1
        for: 5m
        labels:
          severity: critical
  - name: polyvision-delivery
    rules:
      - alert: LowCDNCacheHitRate
        expr: rate(cdn_cache_status_total{status="hit"}[5m]) / rate(cdn_cache_status_total[5m]) < 0.9
        for: 10m
        labels:
          severity: warning
```

---

## Связано с

- [[Load-Balancing]]
- [[DNS-CDN]]
- [[API-Gateway]]
- [[PV-Security]]
- [[PV-Monitoring]]

## Ресурсы

1. AWS - Securing HLS Content: https://docs.aws.amazon.com/mediapackage/latest/ug/security.html
2. Cloudflare Stream Documentation: https://developers.cloudflare.com/stream/
3. Apple HLS Authoring Specification: https://developer.apple.com/documentation/http-live-streaming
4. NGINX Rate Limiting: https://www.nginx.com/blog/rate-limiting-nginx/
5. "Designing Data-Intensive Applications" - Martin Kleppmann
6. Netflix Tech Blog - Video Streaming: https://netflixtechblog.com/
7. Mux Video Documentation: https://docs.mux.com/

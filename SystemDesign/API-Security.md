---
tags:
  - system-design
  - security
  - owasp
  - api
created: 2026-02-17
---

# Безопасность API / API Security: OWASP Top 10

## Что это

Безопасность API — защита бизнес-логики и данных от автоматизированных атак. OWASP API Security Top 10 (2023): BOLA, Broken Auth, Mass Assignment, Resource Consumption, BFLA, SSRF. Ключевые защиты: валидация ввода (Pydantic), rate limiting, security headers, CORS.

---

## Introduction / Введение

API security is critical as APIs expose business logic and sensitive data to the network. Unlike traditional web applications, APIs are designed for machine-to-machine communication, making them targets for automated attacks.

Безопасность API критически важна, поскольку API предоставляют доступ к бизнес-логике и конфиденциальным данным через сеть. В отличие от традиционных веб-приложений, API предназначены для межмашинного взаимодействия.

---

## OWASP API Security Top 10 (2023)

```
┌─────────────────────────────────────────────────────────────────┐
│                    OWASP API Security Top 10 (2023)              │
├─────────────────────────────────────────────────────────────────┤
│  API1:2023  Broken Object Level Authorization (BOLA)            │
│  API2:2023  Broken Authentication                               │
│  API3:2023  Broken Object Property Level Authorization          │
│  API4:2023  Unrestricted Resource Consumption                   │
│  API5:2023  Broken Function Level Authorization (BFLA)          │
│  API6:2023  Unrestricted Access to Sensitive Business Flows     │
│  API7:2023  Server-Side Request Forgery (SSRF)                  │
│  API8:2023  Security Misconfiguration                           │
│  API9:2023  Improper Inventory Management                       │
│  API10:2023 Unsafe Consumption of APIs                          │
└─────────────────────────────────────────────────────────────────┘
```

### API1: Broken Object Level Authorization (BOLA)

The most common API vulnerability. Attackers manipulate object IDs to access other users' data.

```python
# VULNERABLE: No authorization check
@router.get("/matches/{match_id}")
async def get_match(match_id: str):
    return await match_repo.get(match_id)  # Anyone can access any match

# SECURE: Verify resource ownership
@router.get("/matches/{match_id}")
async def get_match(match_id: str, auth: AuthContext = Depends(get_auth_context)):
    match = await match_repo.get(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if match.org_id != auth.org_id:
        logger.warning("BOLA attempt", user_id=auth.user_id,
            requested_match=match_id, user_org=auth.org_id, match_org=match.org_id)
        raise HTTPException(status_code=404, detail="Match not found")
    return match
```

### API3: Broken Object Property Level Authorization

Mass assignment and excessive data exposure:

```python
from pydantic import BaseModel, Field
from typing import Optional

# VULNERABLE: Accepts all fields including internal ones
class MatchUpdateBad(BaseModel):
    title: str
    status: str
    owner_id: str  # Should not be user-modifiable

# SECURE: Explicit field allowlisting
class MatchUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    class Config:
        extra = "forbid"  # Reject unknown fields

class MatchResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    created_at: datetime
    # Exclude: internal_notes, processing_cost, etc.

@router.patch("/matches/{match_id}")
async def update_match(match_id: str, update: MatchUpdateRequest,
    auth: AuthContext = Depends(get_auth_context)) -> MatchResponse:
    match = await match_repo.update(match_id, auth.org_id,
        update.model_dump(exclude_unset=True))
    return MatchResponse.model_validate(match)
```

### API4: Unrestricted Resource Consumption

```python
MAX_PAGE_SIZE = 1000
DEFAULT_PAGE_SIZE = 100

@router.get("/analytics/detections")
async def get_detections(
    match_id: str,
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(get_auth_context)
):
    match = await verify_match_access(match_id, auth)
    async with asyncio.timeout(30):
        results = await detection_repo.get_paginated(match_id, limit=limit, offset=offset)
    return {"data": results, "pagination": {"limit": limit, "offset": offset,
        "total": await detection_repo.count(match_id)}}
```

### API7: Server-Side Request Forgery (SSRF)

```python
import ipaddress
from urllib.parse import urlparse

ALLOWED_HOSTS = {"api.example.com", "cdn.example.com"}
BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
]

def validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Only HTTPS URLs are allowed")
    if parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"Host not allowed: {parsed.hostname}")
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(parsed.hostname))
        for network in BLOCKED_NETWORKS:
            if ip in network:
                raise ValueError("Access to internal networks is forbidden")
    except socket.gaierror:
        raise ValueError("Could not resolve hostname")
    return url
```

---

## Input Validation / Валидация ввода

### Defense in Depth Validation

```
┌─────────────────────────────────────────────────────────────────┐
│                    Input Validation Layers                       │
├─────────────────────────────────────────────────────────────────┤
│  Layer 1: Network/WAF                                           │
│  ├── Block known attack patterns (SQLi, XSS signatures)        │
│  ├── Rate limiting at edge                                      │
│  └── Request size limits                                        │
│                                                                  │
│  Layer 2: API Gateway                                           │
│  ├── Schema validation (OpenAPI spec)                           │
│  ├── Content-Type enforcement                                   │
│  └── Authentication check                                       │
│                                                                  │
│  Layer 3: Application                                           │
│  ├── Pydantic model validation                                  │
│  ├── Business rule validation                                   │
│  └── Authorization checks                                       │
│                                                                  │
│  Layer 4: Database                                              │
│  ├── Parameterized queries (prevent SQLi)                       │
│  ├── Constraints (NOT NULL, UNIQUE, CHECK)                      │
│  └── Type enforcement                                           │
└─────────────────────────────────────────────────────────────────┘
```

### Comprehensive Pydantic Validation

```python
from pydantic import BaseModel, Field, validator, constr
import re

SafeString = constr(min_length=1, max_length=200, pattern=r'^[\w\s\-\.]+$')

class MatchCreateRequest(BaseModel):
    title: SafeString = Field(..., description="Match title")
    description: str | None = Field(None, max_length=5000)
    scheduled_at: datetime
    team_home: str = Field(..., min_length=1, max_length=100)
    team_away: str = Field(..., min_length=1, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=20)

    @validator('scheduled_at')
    def validate_scheduled_at(cls, v):
        if v < datetime.now(timezone.utc):
            raise ValueError('Scheduled time must be in the future')
        return v

    @validator('tags', each_item=True)
    def validate_tags(cls, v):
        if not re.match(r'^[\w\-]{1,50}$', v):
            raise ValueError('Invalid tag format')
        return v.lower()

    @validator('description')
    def sanitize_description(cls, v):
        if v:
            v = re.sub(r'<script[^>]*>.*?</script>', '', v, flags=re.IGNORECASE | re.DOTALL)
            v = re.sub(r'javascript:', '', v, flags=re.IGNORECASE)
        return v

    class Config:
        extra = "forbid"
        str_strip_whitespace = True

# SQL Injection prevention — always parameterized queries
sql = """
    SELECT * FROM matches
    WHERE org_id = $1 AND title ILIKE $2 LIMIT $3
"""
return await db.fetch_all(sql, org_id, f"%{query}%", limit)
```

---

## Rate Limiting / Ограничение запросов

### Rate Limiting Strategies

```
┌─────────────────────────────────────────────────────────────────┐
│                    Rate Limiting Strategies                      │
├─────────────────────────────────────────────────────────────────┤
│  Token Bucket                    Sliding Window                  │
│  + Allows bursts                 + More accurate                 │
│  + Simple implementation         + No burst allowance            │
│                                                                  │
│  Fixed Window                    Leaky Bucket                    │
│  + Very simple                   + Smooths output                │
│  - Boundary spike issues         + Predictable                   │
└─────────────────────────────────────────────────────────────────┘
```

### Redis-Based Sliding Window Rate Limiter

```python
import redis.asyncio as redis
import time

class SlidingWindowRateLimiter:
    def __init__(self, redis_client, requests_per_window, window_seconds):
        self.redis = redis_client
        self.max_requests = requests_per_window
        self.window = window_seconds

    async def check_limit(self, key: str) -> tuple[bool, dict]:
        now = time.time()
        window_start = now - self.window
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, self.window)
        results = await pipe.execute()
        request_count = results[1]
        allowed = request_count < self.max_requests
        remaining = max(0, self.max_requests - request_count - 1)
        return allowed, {
            "X-RateLimit-Limit": self.max_requests,
            "X-RateLimit-Remaining": remaining,
            "X-RateLimit-Reset": int(now + self.window),
        }

RATE_LIMITS = {
    "default": {"requests": 100, "window": 60},
    "auth": {"requests": 10, "window": 60},
    "upload": {"requests": 5, "window": 300},
    "analytics": {"requests": 30, "window": 60},
}
```

### Tiered Rate Limiting

| Tier | Requests/Minute | Use Case |
|------|-----------------|----------|
| Anonymous | 20 | Public endpoints |
| Free | 100 | Authenticated free users |
| Pro | 1000 | Paid subscription |
| Enterprise | 10000 | Enterprise API access |
| Internal | Unlimited | Service-to-service |

---

## Security Headers / Заголовки безопасности

```python
SECURITY_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Cache-Control": "no-store, max-age=0",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
}

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        return response
```

### CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

ALLOWED_ORIGINS = ["https://app.polyvision.io", "https://admin.polyvision.io"]

app.add_middleware(CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-RateLimit-Remaining", "X-RateLimit-Reset"],
    max_age=86400)
```

---

## Logging and Monitoring / Логирование и мониторинг

### Security Event Logging

```python
import structlog

logger = structlog.get_logger()

class SecurityEventLogger:
    @staticmethod
    async def log_authentication_attempt(user_id, success, method, ip_address, user_agent, reason=None):
        await logger.ainfo("authentication_attempt", event_type="security.auth",
            user_id=user_id, success=success, method=method,
            ip_address=ip_address, user_agent=user_agent, reason=reason)

    @staticmethod
    async def log_authorization_failure(user_id, resource, action, ip_address):
        await logger.awarning("authorization_failure", event_type="security.authz",
            user_id=user_id, resource=resource, action=action, ip_address=ip_address)

    @staticmethod
    async def log_suspicious_activity(user_id, activity_type, details, ip_address, severity="medium"):
        await logger.awarning("suspicious_activity", event_type="security.suspicious",
            user_id=user_id, activity_type=activity_type, details=details,
            ip_address=ip_address, severity=severity)

async def detect_brute_force(user_id, ip_address):
    key = f"failed_auth:{ip_address}"
    count = await redis.incr(key)
    await redis.expire(key, 900)
    if count >= 10:
        await SecurityEventLogger.log_suspicious_activity(
            user_id=user_id, activity_type="brute_force_attempt",
            details={"failed_attempts": count}, ip_address=ip_address, severity="high")
        await block_ip_temporarily(ip_address, duration=3600)
```

### API Security Metrics

```python
from prometheus_client import Counter, Histogram

auth_attempts = Counter('auth_attempts_total', 'Authentication attempts', ['method', 'status'])
authz_decisions = Counter('authz_decisions_total', 'Authorization decisions',
    ['resource_type', 'action', 'decision'])
rate_limit_hits = Counter('rate_limit_hits_total', 'Rate limit exceeded', ['endpoint', 'tier'])
request_latency = Histogram('api_request_duration_seconds', 'API request latency',
    ['method', 'endpoint', 'status_code'])
```

---

## Связано с

- [[Authentication]]
- [[Authorization]]
- [[Encryption]]
- [[API-Gateway]]
- [[PV-Security]]

## Ресурсы

1. OWASP API Security Top 10 (2023): https://owasp.org/API-Security/
2. OWASP Input Validation Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html
3. OWASP REST Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html
4. RFC 6585 - Additional HTTP Status Codes (429): https://datatracker.ietf.org/doc/html/rfc6585
5. Mozilla Web Security Guidelines: https://infosec.mozilla.org/guidelines/web_security
6. Cloudflare Rate Limiting: https://developers.cloudflare.com/waf/rate-limiting-rules/
7. FastAPI Security Documentation: https://fastapi.tiangolo.com/tutorial/security/
8. NIST Application Security Guidelines: https://csrc.nist.gov/publications/detail/sp/800-95/final

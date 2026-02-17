---
tags:
  - polyvision
  - system-design
  - security
created: 2026-02-17
---

# Архитектура безопасности Polyvision / Polyvision Security Architecture: Auth Service and Multi-Tenancy Design

## Что это

Архитектура безопасности Polyvision: Auth Service (порт 8001) с OAuth2 (Google/Apple), JWT RS256, мультитенантность через `organizations`, RBAC (viewer/staff/analyst/admin/owner), управление сессиями в Redis, подписки через Stripe (Free/Pro/Enterprise).

---

## Executive Summary / Краткое резюме

Polyvision's security architecture is built around a dedicated Auth Service (port 8001) that handles authentication via OAuth2 social providers (Google, Apple), issues JWTs, and manages user sessions. The multi-tenancy model uses an `organizations` table as the primary tenant boundary, with `organization_memberships` defining user-organization relationships and roles.

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Identity Provider | OAuth2 (Google/Apple) | No password management, trusted identity |
| Token Format | JWT (RS256) | Stateless validation, service-to-service trust |
| Session Storage | Redis (`redis-cache`) | Fast lookup, automatic expiry |
| Tenant Model | Organization-based | Teams share resources, billing per org |
| Role Model | Hierarchical RBAC | Simple, covers 95% of use cases |

---

## Auth Service Design / Дизайн Auth Service

### Service Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Auth Service (:8001)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    API Endpoints                         │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │  POST /auth/oauth/google     - Google OAuth callback    │    │
│  │  POST /auth/oauth/apple      - Apple OAuth callback     │    │
│  │  POST /auth/token/refresh    - Refresh access token     │    │
│  │  POST /auth/logout           - Invalidate session       │    │
│  │  GET  /auth/me               - Current user info        │    │
│  │  GET  /auth/sessions         - List active sessions     │    │
│  │  DELETE /auth/sessions/{id}  - Revoke specific session  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  Core Components                         │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │  OAuth Handler    │  JWT Issuer    │  Session Manager   │    │
│  │  - Provider SDKs  │  - RS256 keys  │  - Redis storage   │    │
│  │  - State/PKCE     │  - Claims      │  - Device tracking │    │
│  │  - User linking   │  - Rotation    │  - Expiry handling │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│            ┌─────────────────┼─────────────────┐                │
│            ▼                 ▼                 ▼                │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐        │
│  │  PostgreSQL  │   │ Redis Cache  │   │    JWKS      │        │
│  │  (users,     │   │ (sessions,   │   │ Endpoint     │        │
│  │   orgs)      │   │  state)      │   │ /.well-known │        │
│  └──────────────┘   └──────────────┘   └──────────────┘        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### OAuth2 Flow Implementation

```
┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐
│  Client  │      │ Gateway  │      │  Auth    │      │  Google/ │
│  (App)   │      │  (BFF)   │      │ Service  │      │  Apple   │
└────┬─────┘      └────┬─────┘      └────┬─────┘      └────┬─────┘
     │                 │                 │                 │
     │  1. Login click │                 │                 │
     │────────────────>│                 │                 │
     │                 │  2. Get auth URL│                 │
     │                 │────────────────>│                 │
     │                 │                 │  3. Store state │
     │                 │                 │  + PKCE verifier│
     │                 │  4. Auth URL    │                 │
     │                 │<────────────────│                 │
     │  5. Redirect    │                 │                 │
     │<────────────────│                 │                 │
     │                 │                 │                 │
     │  6. OAuth consent flow            │                 │
     │─────────────────────────────────────────────────────>
     │                 │                 │                 │
     │  7. Callback with code            │                 │
     │<─────────────────────────────────────────────────────
     │                 │                 │                 │
     │  8. Code + state│                 │                 │
     │────────────────>│                 │                 │
     │                 │  9. Exchange    │                 │
     │                 │────────────────>│                 │
     │                 │                 │ 10. Code→Token  │
     │                 │                 │────────────────>│
     │                 │                 │ 11. ID Token    │
     │                 │                 │<────────────────│
     │                 │                 │                 │
     │                 │                 │ 12. Create/link │
     │                 │                 │     user        │
     │                 │                 │                 │
     │                 │ 13. JWT + Refresh Token           │
     │                 │<────────────────│                 │
     │ 14. Set cookies │                 │                 │
     │<────────────────│                 │                 │
```

### OAuth Provider Configuration

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class OAuthProviderConfig:
    name: str
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    userinfo_url: str
    scopes: list[str]
    jwks_url: Optional[str] = None

OAUTH_PROVIDERS = {
    "google": OAuthProviderConfig(
        name="google",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
        scopes=["openid", "email", "profile"],
        jwks_url="https://www.googleapis.com/oauth2/v3/certs",
    ),
    "apple": OAuthProviderConfig(
        name="apple",
        client_id=os.environ["APPLE_CLIENT_ID"],
        client_secret=os.environ["APPLE_CLIENT_SECRET"],  # Generated JWT
        authorize_url="https://appleid.apple.com/auth/authorize",
        token_url="https://appleid.apple.com/auth/token",
        userinfo_url=None,  # Apple returns user info in ID token
        scopes=["openid", "email", "name"],
        jwks_url="https://appleid.apple.com/auth/keys",
    ),
}
```

---

## Multi-Tenancy Architecture / Архитектура мультитенантности

### Database Schema

```
┌─────────────────────────────────────────────────────────────────┐
│                    Multi-Tenancy Schema                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐                                            │
│  │     users       │                                            │
│  ├─────────────────┤                                            │
│  │ id (PK)         │                                            │
│  │ email           │                                            │
│  │ name            │                                            │
│  │ avatar_url      │                                            │
│  │ created_at      │                                            │
│  │ updated_at      │                                            │
│  │ last_login_at   │                                            │
│  └────────┬────────┘                                            │
│           │                                                      │
│           │ 1:N                                                  │
│           ▼                                                      │
│  ┌─────────────────────────────┐                                │
│  │  organization_memberships   │                                │
│  ├─────────────────────────────┤                                │
│  │ id (PK)                     │                                │
│  │ user_id (FK→users)          │                                │
│  │ organization_id (FK→orgs)   │                                │
│  │ role (enum)                 │────┐                           │
│  │ created_at                  │    │  viewer                   │
│  │ invited_by (FK→users)       │    │  staff                    │
│  └─────────────┬───────────────┘    │  analyst                  │
│                │                     │  admin                    │
│                │ N:1                 │  owner                    │
│                ▼                     │                           │
│  ┌─────────────────┐                │                           │
│  │  organizations  │<───────────────┘                           │
│  ├─────────────────┤                                            │
│  │ id (PK)         │                                            │
│  │ name            │                                            │
│  │ slug (unique)   │                                            │
│  │ logo_url        │                                            │
│  │ created_at      │                                            │
│  │ settings (JSONB)│                                            │
│  └────────┬────────┘                                            │
│           │                                                      │
│           │ 1:N                                                  │
│           ▼                                                      │
│  ┌─────────────────┐      ┌─────────────────┐                   │
│  │  subscriptions  │      │    matches      │                   │
│  ├─────────────────┤      ├─────────────────┤                   │
│  │ id (PK)         │      │ id (PK)         │                   │
│  │ org_id (FK)     │      │ org_id (FK)     │◄── Tenant boundary│
│  │ plan            │      │ title           │                   │
│  │ status          │      │ status          │                   │
│  │ stripe_sub_id   │      │ created_at      │                   │
│  │ current_period  │      │ ...             │                   │
│  └─────────────────┘      └─────────────────┘                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### SQL Schema Definition

```sql
-- Users table (identity)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

-- OAuth provider links
CREATE TABLE user_oauth_providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,  -- 'google', 'apple'
    provider_user_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(provider, provider_user_id)
);

-- Organizations (tenants)
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    logo_url TEXT,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- User-Organization membership with roles
CREATE TYPE org_role AS ENUM ('viewer', 'staff', 'analyst', 'admin', 'owner');

CREATE TABLE organization_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role org_role NOT NULL DEFAULT 'viewer',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    invited_by UUID REFERENCES users(id),
    UNIQUE(user_id, organization_id)
);

-- Row-level security for tenant isolation
ALTER TABLE matches ENABLE ROW LEVEL SECURITY;

CREATE POLICY matches_tenant_isolation ON matches
    USING (org_id = current_setting('app.current_org_id')::UUID);

-- Index for fast membership lookups
CREATE INDEX idx_memberships_user ON organization_memberships(user_id);
CREATE INDEX idx_memberships_org ON organization_memberships(organization_id);
```

### Tenant Context Propagation

```python
from contextvars import ContextVar
from typing import Optional
import asyncpg

# Thread-safe context for current tenant
current_org_id: ContextVar[Optional[str]] = ContextVar('current_org_id', default=None)
current_user_id: ContextVar[Optional[str]] = ContextVar('current_user_id', default=None)

class TenantMiddleware:
    """Extract tenant context from JWT and set for request."""

    async def __call__(self, request, call_next):
        # Extract from JWT claims (set by auth middleware)
        auth_context = getattr(request.state, 'auth', None)

        if auth_context:
            current_org_id.set(auth_context.org_id)
            current_user_id.set(auth_context.user_id)

        try:
            response = await call_next(request)
            return response
        finally:
            # Clean up context
            current_org_id.set(None)
            current_user_id.set(None)

class TenantAwareConnection:
    """Database connection with tenant context."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def acquire(self):
        conn = await self.pool.acquire()

        # Set tenant context for RLS policies
        org_id = current_org_id.get()
        if org_id:
            await conn.execute(
                f"SET app.current_org_id = '{org_id}'"
            )

        return conn
```

---

## Role-Based Access Control / Ролевое управление доступом

### Role Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                    Polyvision Role Hierarchy                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│                         ┌─────────┐                             │
│                         │  Owner  │ ← One per organization      │
│                         └────┬────┘                             │
│                              │ inherits                         │
│                              ▼                                   │
│                         ┌─────────┐                             │
│                         │  Admin  │ ← Manage users, settings    │
│                         └────┬────┘                             │
│                              │                                   │
│              ┌───────────────┼───────────────┐                  │
│              │ inherits      │ inherits      │                  │
│              ▼               ▼               ▼                  │
│         ┌─────────┐    ┌─────────┐    ┌─────────┐              │
│         │  Staff  │    │ Analyst │    │ (other) │              │
│         └────┬────┘    └────┬────┘    └─────────┘              │
│              │              │                                    │
│              │ inherits     │ inherits                          │
│              │              │                                    │
│              └──────┬───────┘                                   │
│                     ▼                                            │
│                ┌─────────┐                                      │
│                │ Viewer  │ ← Base permissions                   │
│                └─────────┘                                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Permission Matrix

| Permission | Viewer | Staff | Analyst | Admin | Owner |
|------------|--------|-------|---------|-------|-------|
| View matches | Y | Y | Y | Y | Y |
| View analytics | Y | Y | Y | Y | Y |
| Upload footage | - | Y | - | Y | Y |
| Edit matches | - | Y | - | Y | Y |
| Delete matches | - | - | - | Y | Y |
| Export analytics | - | - | Y | Y | Y |
| Manage users | - | - | - | Y | Y |
| Manage billing | - | - | - | - | Y |
| Delete organization | - | - | - | - | Y |

### Implementation

```python
from enum import Enum
from typing import Set

class Role(str, Enum):
    VIEWER = "viewer"
    STAFF = "staff"
    ANALYST = "analyst"
    ADMIN = "admin"
    OWNER = "owner"

class Permission(str, Enum):
    # Match permissions
    MATCH_VIEW = "match:view"
    MATCH_CREATE = "match:create"
    MATCH_UPDATE = "match:update"
    MATCH_DELETE = "match:delete"

    # Analytics permissions
    ANALYTICS_VIEW = "analytics:view"
    ANALYTICS_EXPORT = "analytics:export"

    # Organization management
    ORG_INVITE_USERS = "org:invite_users"
    ORG_REMOVE_USERS = "org:remove_users"
    ORG_MANAGE_ROLES = "org:manage_roles"
    ORG_MANAGE_BILLING = "org:manage_billing"
    ORG_MANAGE_SETTINGS = "org:manage_settings"
    ORG_DELETE = "org:delete"

# Role → Permissions mapping
ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    Role.VIEWER: {
        Permission.MATCH_VIEW,
        Permission.ANALYTICS_VIEW,
    },

    Role.STAFF: {
        Permission.MATCH_VIEW,
        Permission.MATCH_CREATE,
        Permission.MATCH_UPDATE,
        Permission.ANALYTICS_VIEW,
    },

    Role.ANALYST: {
        Permission.MATCH_VIEW,
        Permission.ANALYTICS_VIEW,
        Permission.ANALYTICS_EXPORT,
    },

    Role.ADMIN: {
        Permission.MATCH_VIEW,
        Permission.MATCH_CREATE,
        Permission.MATCH_UPDATE,
        Permission.MATCH_DELETE,
        Permission.ANALYTICS_VIEW,
        Permission.ANALYTICS_EXPORT,
        Permission.ORG_INVITE_USERS,
        Permission.ORG_REMOVE_USERS,
        Permission.ORG_MANAGE_ROLES,
        Permission.ORG_MANAGE_SETTINGS,
    },

    Role.OWNER: set(Permission),  # All permissions
}

def get_permissions(role: Role) -> Set[Permission]:
    """Get all permissions for a role (including inherited)."""
    return ROLE_PERMISSIONS.get(role, set())

def has_permission(role: Role, permission: Permission) -> bool:
    """Check if a role has a specific permission."""
    return permission in get_permissions(role)
```

---

## Token Management / Управление токенами

### JWT Claims Structure

```python
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt

@dataclass
class TokenClaims:
    # Standard claims
    iss: str  # "https://auth.polyvision.io"
    sub: str  # User ID
    aud: str  # "polyvision-api"
    exp: int  # Expiration timestamp
    iat: int  # Issued at timestamp
    jti: str  # Token ID (for revocation)

    # Custom claims
    org_id: str           # Current organization context
    role: str             # Role in current organization
    email: str            # User email
    name: str             # User display name

class JWTIssuer:
    def __init__(
        self,
        private_key: str,
        public_key: str,
        issuer: str = "https://auth.polyvision.io",
        audience: str = "polyvision-api",
        access_token_ttl: int = 900,      # 15 minutes
        refresh_token_ttl: int = 604800,   # 7 days
    ):
        self.private_key = private_key
        self.public_key = public_key
        self.issuer = issuer
        self.audience = audience
        self.access_token_ttl = access_token_ttl
        self.refresh_token_ttl = refresh_token_ttl

    def create_access_token(
        self,
        user_id: str,
        org_id: str,
        role: str,
        email: str,
        name: str
    ) -> str:
        """Create short-lived access token."""
        now = datetime.now(timezone.utc)

        claims = {
            "iss": self.issuer,
            "sub": user_id,
            "aud": self.audience,
            "exp": int((now + timedelta(seconds=self.access_token_ttl)).timestamp()),
            "iat": int(now.timestamp()),
            "jti": str(uuid.uuid4()),
            "org_id": org_id,
            "role": role,
            "email": email,
            "name": name,
        }

        return jwt.encode(claims, self.private_key, algorithm="RS256")

    def create_refresh_token(self, user_id: str, session_id: str) -> str:
        """Create long-lived refresh token (stored in DB)."""
        now = datetime.now(timezone.utc)

        claims = {
            "iss": self.issuer,
            "sub": user_id,
            "aud": self.audience,
            "exp": int((now + timedelta(seconds=self.refresh_token_ttl)).timestamp()),
            "iat": int(now.timestamp()),
            "jti": str(uuid.uuid4()),
            "sid": session_id,  # Session ID for revocation
            "type": "refresh",
        }

        return jwt.encode(claims, self.private_key, algorithm="RS256")
```

### Session Storage

```python
import json
from datetime import timedelta
from typing import Optional

class SessionManager:
    def __init__(self, redis: Redis, ttl: int = 86400):
        self.redis = redis
        self.ttl = ttl  # 24 hours default

    async def create_session(
        self,
        user_id: str,
        org_id: str,
        device_info: dict
    ) -> str:
        """Create new session and store in Redis."""
        session_id = str(uuid.uuid4())

        session_data = {
            "user_id": user_id,
            "org_id": org_id,
            "created_at": datetime.utcnow().isoformat(),
            "last_active": datetime.utcnow().isoformat(),
            "device": device_info,
        }

        # Store session
        await self.redis.setex(
            f"session:{session_id}",
            timedelta(seconds=self.ttl),
            json.dumps(session_data)
        )

        # Track user's sessions (for listing/revocation)
        await self.redis.sadd(f"user_sessions:{user_id}", session_id)

        return session_id

    async def get_session(self, session_id: str) -> Optional[dict]:
        """Get session data."""
        data = await self.redis.get(f"session:{session_id}")
        if data:
            return json.loads(data)
        return None

    async def revoke_session(self, session_id: str):
        """Revoke a specific session."""
        session = await self.get_session(session_id)
        if session:
            await self.redis.delete(f"session:{session_id}")
            await self.redis.srem(
                f"user_sessions:{session['user_id']}",
                session_id
            )

    async def revoke_all_sessions(self, user_id: str):
        """Revoke all sessions for a user (logout everywhere)."""
        session_ids = await self.redis.smembers(f"user_sessions:{user_id}")

        for session_id in session_ids:
            await self.redis.delete(f"session:{session_id}")

        await self.redis.delete(f"user_sessions:{user_id}")
```

---

## Subscriptions and Entitlements / Подписки и права

### Subscription Model

```
┌─────────────────────────────────────────────────────────────────┐
│                    Subscription Architecture                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  Stripe Integration                      │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │  Webhook Events:                                        │    │
│  │  - customer.subscription.created                        │    │
│  │  - customer.subscription.updated                        │    │
│  │  - customer.subscription.deleted                        │    │
│  │  - invoice.paid                                         │    │
│  │  - invoice.payment_failed                               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   subscriptions table                    │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │  id              │ UUID                                 │    │
│  │  org_id          │ FK → organizations                   │    │
│  │  stripe_cust_id  │ cus_xxx                              │    │
│  │  stripe_sub_id   │ sub_xxx                              │    │
│  │  plan            │ free | pro | enterprise              │    │
│  │  status          │ active | past_due | canceled         │    │
│  │  current_period_start │ TIMESTAMPTZ                     │    │
│  │  current_period_end   │ TIMESTAMPTZ                     │    │
│  │  cancel_at_period_end │ BOOLEAN                         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Plan Entitlements                      │    │
│  ├─────────────────────────────────────────────────────────┤    │
│  │                                                          │    │
│  │  Free:       5 matches/mo, 720p, 7-day retention        │    │
│  │  Pro:        50 matches/mo, 1080p, 30-day retention     │    │
│  │  Enterprise: Unlimited, 4K, 90-day, API access          │    │
│  │                                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Entitlement Checking

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional

class Plan(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"

@dataclass
class PlanLimits:
    matches_per_month: int
    max_resolution: str
    retention_days: int
    api_access: bool
    priority_processing: bool

PLAN_LIMITS: dict[Plan, PlanLimits] = {
    Plan.FREE: PlanLimits(
        matches_per_month=5,
        max_resolution="720p",
        retention_days=7,
        api_access=False,
        priority_processing=False,
    ),
    Plan.PRO: PlanLimits(
        matches_per_month=50,
        max_resolution="1080p",
        retention_days=30,
        api_access=True,
        priority_processing=False,
    ),
    Plan.ENTERPRISE: PlanLimits(
        matches_per_month=-1,  # Unlimited
        max_resolution="4k",
        retention_days=90,
        api_access=True,
        priority_processing=True,
    ),
}

class EntitlementService:
    def __init__(self, db, redis):
        self.db = db
        self.redis = redis

    async def get_org_plan(self, org_id: str) -> Plan:
        """Get organization's current plan."""
        # Check cache first
        cached = await self.redis.get(f"plan:{org_id}")
        if cached:
            return Plan(cached)

        # Query database
        sub = await self.db.fetch_one(
            """
            SELECT plan FROM subscriptions
            WHERE org_id = $1 AND status = 'active'
            ORDER BY created_at DESC LIMIT 1
            """,
            org_id
        )

        plan = Plan(sub["plan"]) if sub else Plan.FREE

        # Cache for 5 minutes
        await self.redis.setex(f"plan:{org_id}", 300, plan.value)

        return plan

    async def check_match_limit(self, org_id: str) -> tuple[bool, int]:
        """Check if org can create more matches this month."""
        plan = await self.get_org_plan(org_id)
        limits = PLAN_LIMITS[plan]

        if limits.matches_per_month == -1:
            return True, -1  # Unlimited

        # Count matches this month
        count = await self.db.fetch_val(
            """
            SELECT COUNT(*) FROM matches
            WHERE org_id = $1
            AND created_at >= date_trunc('month', CURRENT_DATE)
            """,
            org_id
        )

        remaining = limits.matches_per_month - count
        return remaining > 0, remaining

    async def check_api_access(self, org_id: str) -> bool:
        """Check if org has API access entitlement."""
        plan = await self.get_org_plan(org_id)
        return PLAN_LIMITS[plan].api_access
```

---

## Security Considerations / Вопросы безопасности

### Security Checklist

- [x] **OAuth2 with PKCE** for all authentication flows
- [x] **Short-lived access tokens** (15 minutes) with refresh token rotation
- [x] **Secure cookie storage** for refresh tokens (HTTP-only, Secure, SameSite)
- [x] **Row-level security** in PostgreSQL for tenant isolation
- [x] **Rate limiting** on auth endpoints (10 req/min)
- [x] **Account lockout** after 5 failed attempts
- [x] **Session tracking** with device information
- [x] **Audit logging** for all auth events
- [x] **mTLS** for service-to-service communication

### Threat Mitigations

| Threat | Mitigation |
|--------|------------|
| Token theft | Short expiry, secure storage, refresh rotation |
| Session hijacking | Device fingerprinting, IP binding |
| Privilege escalation | Server-side role validation, RLS |
| Tenant data leak | Organization-scoped queries, RLS policies |
| Brute force | Rate limiting, account lockout |
| OAuth state attacks | PKCE, state parameter validation |

---

## Связано с

- [[Authentication]]
- [[Authorization]]
- [[Encryption]]
- [[API-Security]]
- [[PV-Networking]]
- [[PV-Monitoring]]

## Ресурсы

1. RFC 6749 - OAuth 2.0 Authorization Framework: https://datatracker.ietf.org/doc/html/rfc6749
2. RFC 7636 - PKCE for OAuth: https://datatracker.ietf.org/doc/html/rfc7636
3. Sign in with Apple Documentation: https://developer.apple.com/sign-in-with-apple/
4. Google Identity OAuth 2.0: https://developers.google.com/identity/protocols/oauth2
5. PostgreSQL Row Level Security: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
6. Stripe Subscriptions API: https://stripe.com/docs/billing/subscriptions
7. OWASP Multi-Tenancy Security: https://cheatsheetseries.owasp.org/cheatsheets/Multitenant_Architecture_Security_Cheat_Sheet.html
8. NIST SP 800-63B - Digital Identity Guidelines: https://pages.nist.gov/800-63-3/sp800-63b.html

---
tags:
  - system-design
  - security
  - authorization
  - rbac
created: 2026-02-17
---

# Авторизация / Authorization: RBAC, ABAC, ReBAC

## Что это

Авторизация определяет, какие действия аутентифицированный пользователь может выполнять над ресурсами. Эволюция моделей: ACL -> RBAC -> ABAC -> ReBAC. Ключевые движки: OPA/Rego, Cedar, SpiceDB, Casbin.

---

## Introduction / Введение

Authorization determines what actions an authenticated user can perform on which resources. While authentication answers "Who are you?", authorization answers "What can you do?". Modern systems require flexible authorization models that can handle complex business rules while maintaining performance and auditability.

Авторизация определяет, какие действия аутентифицированный пользователь может выполнять над ресурсами. Если аутентификация отвечает на вопрос "Кто вы?", то авторизация отвечает "Что вы можете делать?".

---

## Authorization Models / Модели авторизации

### Evolution of Access Control

```
┌─────────────────────────────────────────────────────────────────┐
│                    Authorization Evolution                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ACL (1970s)    RBAC (1990s)    ABAC (2000s)    ReBAC (2010s)   │
│  ────────────────────────────────────────────────────────────>  │
│                                                                  │
│  User→Resource  User→Role       User+Context    User→Relation   │
│                 Role→Permission →Permission     →Resource       │
│                                                                  │
│  Simple         Scalable        Dynamic         Graph-based     │
│  Static         Hierarchical    Policy-driven   Fine-grained    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Model Comparison

| Aspect | ACL | RBAC | ABAC | ReBAC |
|--------|-----|------|------|-------|
| Granularity | Resource | Role | Attribute | Relationship |
| Scalability | Poor | Good | Good | Excellent |
| Flexibility | Low | Medium | High | High |
| Complexity | Low | Medium | High | High |
| Use Case | Files, folders | Enterprise apps | Cloud platforms | Social, collaboration |

---

## Role-Based Access Control / Ролевое управление доступом

### RBAC Core Components

```
┌─────────┐     ┌─────────┐     ┌────────────┐     ┌───────────┐
│  Users  │────>│  Roles  │────>│ Permissions│────>│ Resources │
└─────────┘     └─────────┘     └────────────┘     └───────────┘
     │               │                                    │
     │         ┌─────┴─────┐                             │
     │         │ Hierarchy │                             │
     │         └───────────┘                             │
     │               │                                    │
     └───────────────┴────────────────────────────────────┘
                    Constraints (SoD, time-based)
```

### RBAC Levels (NIST)

| Level | Name | Features |
|-------|------|----------|
| RBAC0 | Flat RBAC | Users, roles, permissions, sessions |
| RBAC1 | Hierarchical | Role inheritance (senior inherits junior) |
| RBAC2 | Constrained | Separation of Duties, cardinality limits |
| RBAC3 | Symmetric | Combines RBAC1 + RBAC2 |

### Role Hierarchy Example

```
                    ┌─────────────┐
                    │   Owner     │
                    │ (all perms) │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────┴─────┐ ┌────┴────┐ ┌─────┴─────┐
        │   Admin   │ │ Analyst │ │  Staff    │
        │(manage)   │ │(analyze)│ │ (view+)   │
        └─────┬─────┘ └────┬────┘ └─────┬─────┘
              │            │            │
              └────────────┼────────────┘
                           │
                     ┌─────┴─────┐
                     │  Viewer   │
                     │ (read)    │
                     └───────────┘
```

### RBAC Implementation

```python
from enum import Enum
from dataclasses import dataclass
from typing import Set

class Permission(Enum):
    MATCH_VIEW = "match:view"
    MATCH_CREATE = "match:create"
    MATCH_UPDATE = "match:update"
    MATCH_DELETE = "match:delete"
    ANALYTICS_VIEW = "analytics:view"
    ANALYTICS_EXPORT = "analytics:export"
    ORG_MANAGE_USERS = "org:manage_users"
    ORG_MANAGE_BILLING = "org:manage_billing"
    ORG_MANAGE_SETTINGS = "org:manage_settings"

class Role(Enum):
    VIEWER = "viewer"
    STAFF = "staff"
    ANALYST = "analyst"
    ADMIN = "admin"
    OWNER = "owner"

ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    Role.VIEWER: {Permission.MATCH_VIEW},
    Role.STAFF: {Permission.MATCH_VIEW, Permission.MATCH_CREATE,
                 Permission.MATCH_UPDATE, Permission.ANALYTICS_VIEW},
    Role.ANALYST: {Permission.MATCH_VIEW, Permission.ANALYTICS_VIEW,
                   Permission.ANALYTICS_EXPORT},
    Role.ADMIN: {Permission.MATCH_VIEW, Permission.MATCH_CREATE,
                 Permission.MATCH_UPDATE, Permission.MATCH_DELETE,
                 Permission.ANALYTICS_VIEW, Permission.ANALYTICS_EXPORT,
                 Permission.ORG_MANAGE_USERS, Permission.ORG_MANAGE_SETTINGS},
    Role.OWNER: set(Permission),  # All permissions
}

@dataclass
class AuthContext:
    user_id: str
    org_id: str
    roles: Set[Role]

    def has_permission(self, permission: Permission) -> bool:
        for role in self.roles:
            if permission in ROLE_PERMISSIONS.get(role, set()):
                return True
        return False

# FastAPI dependency
async def require_permission(permission: Permission):
    async def check(auth: AuthContext = Depends(get_auth_context)):
        if not auth.has_permission(permission):
            raise HTTPException(status_code=403,
                detail=f"Missing required permission: {permission.value}")
        return auth
    return check

@router.delete("/matches/{match_id}")
async def delete_match(
    match_id: str,
    auth: AuthContext = Depends(require_permission(Permission.MATCH_DELETE))
):
    await match_service.delete(match_id, auth.org_id)
```

---

## Attribute-Based Access Control / Атрибутное управление доступом

### ABAC Components

ABAC evaluates access based on attributes of the subject, resource, action, and environment:

```
┌─────────────────────────────────────────────────────────────┐
│                      Policy Decision                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Subject Attrs     Resource Attrs    Action     Environment │
│  ┌───────────┐    ┌─────────────┐   ┌──────┐   ┌──────────┐│
│  │ user_id   │    │ resource_id │   │ read │   │ time     ││
│  │ role      │    │ owner       │   │ write│   │ ip_addr  ││
│  │ department│    │ sensitivity │   │delete│   │ location ││
│  │ clearance │    │ created_at  │   │      │   │ device   ││
│  └───────────┘    └─────────────┘   └──────┘   └──────────┘│
│        │                │               │            │      │
│        └────────────────┴───────────────┴────────────┘      │
│                              │                               │
│                        ┌─────┴─────┐                        │
│                        │  Policy   │                        │
│                        │  Engine   │                        │
│                        └─────┬─────┘                        │
│                              │                               │
│                    ┌─────────┴─────────┐                    │
│                    │ PERMIT / DENY     │                    │
│                    └───────────────────┘                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### XACML Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│     PEP     │───>│     PDP     │<───│     PAP     │
│ Enforcement │    │  Decision   │    │   Admin     │
└─────────────┘    └──────┬──────┘    └─────────────┘
                          │
              ┌───────────┼───────────┐
              │           │           │
        ┌─────┴─────┐ ┌───┴───┐ ┌─────┴─────┐
        │    PIP    │ │Context│ │   PRP     │
        │   Info    │ │Handler│ │  Policy   │
        └───────────┘ └───────┘ └───────────┘

PEP: Policy Enforcement Point (where access is requested)
PDP: Policy Decision Point (evaluates policies)
PAP: Policy Administration Point (manages policies)
PIP: Policy Information Point (retrieves attributes)
PRP: Policy Retrieval Point (stores policies)
```

### ABAC Policy Example

```python
from dataclasses import dataclass
from typing import Any, Callable
from datetime import datetime, time

@dataclass
class PolicyContext:
    subject: dict[str, Any]
    resource: dict[str, Any]
    action: str
    environment: dict[str, Any]

class Policy:
    def __init__(self, name: str, effect: str, condition: Callable):
        self.name = name
        self.effect = effect  # "permit" or "deny"
        self.condition = condition

    def evaluate(self, ctx: PolicyContext) -> str | None:
        if self.condition(ctx):
            return self.effect
        return None

policies = [
    Policy("business-hours-only", "deny",
        lambda ctx: ctx.subject.get("role") != "admin" and
            not (time(9, 0) <= datetime.now().time() <= time(18, 0))),
    Policy("owner-access", "permit",
        lambda ctx: ctx.subject.get("user_id") == ctx.resource.get("owner_id")),
    Policy("org-admin-access", "permit",
        lambda ctx: ctx.subject.get("role") == "admin" and
            ctx.subject.get("org_id") == ctx.resource.get("org_id")),
    Policy("clearance-required", "deny",
        lambda ctx: ctx.resource.get("sensitivity") == "high" and
            ctx.subject.get("clearance_level", 0) < 3),
]

def evaluate_policies(ctx: PolicyContext) -> bool:
    """Evaluate all policies, deny-overrides combining algorithm."""
    for policy in policies:
        result = policy.evaluate(ctx)
        if result == "deny":
            return False
    return any(p.evaluate(ctx) == "permit" for p in policies)
```

---

## Relationship-Based Access Control / Реляционное управление доступом

### ReBAC Concepts

ReBAC (Zanzibar-style authorization) models permissions as relationships in a graph:

```
┌─────────────────────────────────────────────────────────────┐
│                    Relationship Graph                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│     user:alice                    organization:acme          │
│         │                               │                    │
│         │ member                        │ parent             │
│         ▼                               ▼                    │
│     team:engineering              team:engineering           │
│         │                               │                    │
│         │ viewer                        │ owner              │
│         ▼                               ▼                    │
│     match:finals2024              match:finals2024           │
│                                                              │
│  Query: Can alice view match:finals2024?                    │
│  Answer: Yes (alice -> team:engineering -> match viewer)    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Tuple-Based Model

```
# Relationship tuples: (object, relation, subject)

# Direct relationships
organization:acme#member@user:alice
organization:acme#admin@user:bob
team:engineering#member@organization:acme#member  # Inherited

# Resource permissions
match:finals2024#owner@organization:acme
match:finals2024#viewer@team:engineering#member
match:finals2024#editor@user:carol
```

### SpiceDB/Zanzibar Implementation

```yaml
# Schema definition (SpiceDB format)
definition organization {
    relation member: user
    relation admin: user
    permission view = member + admin
    permission manage = admin
}

definition team {
    relation parent: organization
    relation member: user | organization#member
    permission view = member + parent->view
}

definition match {
    relation organization: organization
    relation owner: user | organization#admin
    relation editor: user | team#member
    relation viewer: user | team#member | organization#member
    permission view = viewer + editor + owner + organization->view
    permission edit = editor + owner
    permission delete = owner
}
```

---

## Policy Engines / Движки политик

### Open Policy Agent (OPA)

OPA uses Rego, a declarative query language for policy decisions:

```rego
# policy.rego
package polyvision.authz

import future.keywords.if
import future.keywords.in

default allow := false

allow if {
    input.user.role == "owner"
    input.resource.org_id == input.user.org_id
}

allow if {
    input.action == "read"
    input.resource.type == "match"
    "viewer" in input.user.roles
    input.resource.org_id == input.user.org_id
}

allow if {
    input.action in ["create", "update"]
    input.resource.type == "match"
    "staff" in input.user.roles
    input.resource.org_id == input.user.org_id
}

deny if {
    input.resource.deleted == true
    not "admin" in input.user.roles
}

authorized if {
    allow
    not deny
}
```

### OPA Integration with FastAPI

```python
import httpx
from fastapi import Request, HTTPException

class OPAAuthorizationMiddleware:
    def __init__(self, opa_url: str = "http://localhost:8181"):
        self.opa_url = opa_url
        self.client = httpx.AsyncClient()

    async def check_permission(self, user: dict, resource: dict, action: str) -> bool:
        input_data = {"input": {"user": user, "resource": resource, "action": action}}
        response = await self.client.post(
            f"{self.opa_url}/v1/data/polyvision/authz/authorized", json=input_data)
        result = response.json()
        return result.get("result", False)

opa = OPAAuthorizationMiddleware()

@router.get("/matches/{match_id}")
async def get_match(match_id: str, auth: AuthContext = Depends(get_auth)):
    match = await match_repo.get(match_id)
    allowed = await opa.check_permission(
        user={"id": auth.user_id, "roles": auth.roles, "org_id": auth.org_id},
        resource={"type": "match", "id": match_id, "org_id": match.org_id},
        action="read")
    if not allowed:
        raise HTTPException(status_code=403, detail="Access denied")
    return match
```

### Policy Engine Comparison

| Feature | OPA/Rego | Cedar | SpiceDB | Casbin |
|---------|----------|-------|---------|--------|
| Model | ABAC | ABAC | ReBAC | Multiple |
| Language | Rego | Cedar | YAML/gRPC | Conf/API |
| Performance | Fast | Very Fast | Very Fast | Fast |
| Complexity | Medium | Low | Medium | Low |
| Use Case | K8s, APIs | AWS, APIs | Google-scale | General |

---

## Implementation Patterns / Паттерны реализации

### Caching Authorization Decisions

```python
class CachedAuthorizer:
    def __init__(self, policy_engine, cache_ttl: int = 60):
        self.policy_engine = policy_engine
        self.cache = {}
        self.cache_ttl = cache_ttl

    def _cache_key(self, user_id: str, resource: str, action: str) -> str:
        data = f"{user_id}:{resource}:{action}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    async def check(self, user_id: str, resource: str, action: str) -> bool:
        cache_key = self._cache_key(user_id, resource, action)
        cached = self.cache.get(cache_key)
        if cached and cached["expires"] > time.time():
            return cached["decision"]
        decision = await self.policy_engine.check(user_id, resource, action)
        self.cache[cache_key] = {"decision": decision, "expires": time.time() + self.cache_ttl}
        return decision
```

### Audit Logging

```python
import structlog

logger = structlog.get_logger()

async def log_authorization_decision(user_id, resource, action, decision, reason=None):
    await logger.ainfo("authorization_decision",
        user_id=user_id, resource=resource, action=action,
        decision="granted" if decision else "denied",
        reason=reason, timestamp=datetime.utcnow().isoformat())
    await audit_repo.insert({
        "user_id": user_id, "resource": resource, "action": action,
        "decision": decision, "reason": reason, "timestamp": datetime.utcnow()})
```

---

## Связано с

- [[Authentication]]
- [[API-Security]]
- [[PV-Security]]

## Ресурсы

1. NIST RBAC Model: https://csrc.nist.gov/projects/role-based-access-control
2. XACML 3.0 Specification (OASIS): https://docs.oasis-open.org/xacml/3.0/xacml-3.0-core-spec-os-en.html
3. Google Zanzibar Paper: https://research.google/pubs/pub48190/
4. Open Policy Agent Documentation: https://www.openpolicyagent.org/docs/latest/
5. AWS Cedar Policy Language: https://docs.cedarpolicy.com/
6. SpiceDB Documentation: https://authzed.com/docs/spicedb
7. Casbin Authorization Library: https://casbin.org/docs/overview
8. OWASP Access Control Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Access_Control_Cheat_Sheet.html

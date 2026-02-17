---
tags:
  - system-design
  - security
  - authentication
  - oauth
  - jwt
created: 2026-02-17
---

# Аутентификация / Authentication: OAuth2, OIDC, JWT

## Что это

Аутентификация — процесс проверки личности пользователя или системы. Ключевые протоколы: OAuth 2.0 (авторизация), OpenID Connect (идентификация), JWT (токены). PKCE обязателен для публичных клиентов (SPA, мобильные).

---

## Introduction / Введение

Authentication is the process of verifying the identity of a user, device, or system. In modern distributed systems, authentication has evolved from simple username/password combinations to sophisticated protocols that enable secure, federated identity management across multiple services and platforms.

Аутентификация — это процесс проверки личности пользователя, устройства или системы. В современных распределённых системах аутентификация эволюционировала от простых комбинаций логин/пароль до сложных протоколов, обеспечивающих безопасное федеративное управление идентификацией.

---

## OAuth 2.0 Framework / Фреймворк OAuth 2.0

### Core Concepts / Основные концепции

OAuth 2.0 is an authorization framework that enables third-party applications to obtain limited access to user accounts on HTTP services.

```
+--------+                               +---------------+
|        |--(A)- Authorization Request ->|   Resource    |
|        |                               |     Owner     |
|        |<-(B)-- Authorization Grant ---|               |
|        |                               +---------------+
|        |
|        |                               +---------------+
|        |--(C)-- Authorization Grant -->| Authorization |
| Client |                               |     Server    |
|        |<-(D)----- Access Token -------|               |
|        |                               +---------------+
|        |
|        |                               +---------------+
|        |--(E)----- Access Token ------>|    Resource   |
|        |                               |     Server    |
|        |<-(F)--- Protected Resource ---|               |
+--------+                               +---------------+
```

### Grant Types / Типы грантов

| Grant Type | Use Case | Security Level |
|------------|----------|----------------|
| Authorization Code | Server-side apps, SPAs with PKCE | High |
| Client Credentials | Machine-to-machine | High |
| Refresh Token | Token renewal | Medium |
| ~~Implicit~~ | Deprecated (use Auth Code + PKCE) | Low |
| ~~Password~~ | Deprecated (legacy systems only) | Low |

### Authorization Code Flow with PKCE

PKCE (Proof Key for Code Exchange) is mandatory for public clients (mobile apps, SPAs):

```python
import hashlib
import base64
import secrets

def generate_pkce_pair():
    """Generate code_verifier and code_challenge for PKCE."""
    # Generate random code verifier (43-128 characters)
    code_verifier = secrets.token_urlsafe(32)

    # Create SHA256 hash of verifier
    code_challenge_bytes = hashlib.sha256(
        code_verifier.encode('ascii')
    ).digest()

    # Base64url encode without padding
    code_challenge = base64.urlsafe_b64encode(
        code_challenge_bytes
    ).decode('ascii').rstrip('=')

    return code_verifier, code_challenge

# Usage in authorization request
verifier, challenge = generate_pkce_pair()

auth_url = (
    f"https://auth.example.com/authorize"
    f"?response_type=code"
    f"&client_id={client_id}"
    f"&redirect_uri={redirect_uri}"
    f"&scope=openid profile email"
    f"&code_challenge={challenge}"
    f"&code_challenge_method=S256"
    f"&state={state}"
)
```

### Token Exchange Flow

```
┌──────────┐      ┌──────────────┐      ┌─────────────┐
│  Client  │      │  Auth Server │      │  Resource   │
│  (App)   │      │              │      │   Server    │
└────┬─────┘      └──────┬───────┘      └──────┬──────┘
     │                   │                     │
     │  1. Auth Request  │                     │
     │  + code_challenge │                     │
     │──────────────────>│                     │
     │                   │                     │
     │  2. Auth Code     │                     │
     │<──────────────────│                     │
     │                   │                     │
     │  3. Token Request │                     │
     │  + code_verifier  │                     │
     │──────────────────>│                     │
     │                   │                     │
     │  4. Access Token  │                     │
     │  + Refresh Token  │                     │
     │<──────────────────│                     │
     │                   │                     │
     │  5. API Request   │                     │
     │  + Access Token   │                     │
     │─────────────────────────────────────────>
     │                   │                     │
     │  6. Protected     │                     │
     │     Resource      │                     │
     │<─────────────────────────────────────────
```

---

## OpenID Connect / OpenID Connect

### Building on OAuth 2.0

OpenID Connect (OIDC) is an identity layer built on top of OAuth 2.0. While OAuth 2.0 handles authorization (what can you access), OIDC handles authentication (who are you).

```
┌─────────────────────────────────────────────────────┐
│                   OpenID Connect                     │
├─────────────────────────────────────────────────────┤
│  ID Token  │  UserInfo  │  Discovery  │  Session    │
├─────────────────────────────────────────────────────┤
│                     OAuth 2.0                        │
├─────────────────────────────────────────────────────┤
│                       HTTP                           │
└─────────────────────────────────────────────────────┘
```

### ID Token Structure

The ID Token is a JWT containing user identity claims:

```json
{
  "header": {
    "alg": "RS256",
    "typ": "JWT",
    "kid": "key-id-123"
  },
  "payload": {
    "iss": "https://auth.example.com",
    "sub": "user-uuid-12345",
    "aud": "client-id-abc",
    "exp": 1704067200,
    "iat": 1704063600,
    "nonce": "random-nonce-value",
    "email": "user@example.com",
    "email_verified": true,
    "name": "John Doe"
  }
}
```

### Standard Claims

| Claim | Description | Required |
|-------|-------------|----------|
| `iss` | Issuer identifier | Yes |
| `sub` | Subject (user) identifier | Yes |
| `aud` | Audience (client ID) | Yes |
| `exp` | Expiration time | Yes |
| `iat` | Issued at time | Yes |
| `nonce` | Replay prevention | Conditional |
| `auth_time` | Time of authentication | Optional |
| `acr` | Authentication context class | Optional |

### Discovery Endpoint

OIDC providers expose a discovery document at `/.well-known/openid-configuration`:

```json
{
  "issuer": "https://auth.example.com",
  "authorization_endpoint": "https://auth.example.com/authorize",
  "token_endpoint": "https://auth.example.com/token",
  "userinfo_endpoint": "https://auth.example.com/userinfo",
  "jwks_uri": "https://auth.example.com/.well-known/jwks.json",
  "scopes_supported": ["openid", "profile", "email"],
  "response_types_supported": ["code", "token", "id_token"],
  "grant_types_supported": ["authorization_code", "refresh_token"],
  "subject_types_supported": ["public"],
  "id_token_signing_alg_values_supported": ["RS256", "ES256"]
}
```

---

## JSON Web Tokens / JSON Web Токены

### JWT Structure

JWTs consist of three Base64URL-encoded parts separated by dots:

```
Header.Payload.Signature

eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.
eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0.
Signature_Here
```

### Signing Algorithms

| Algorithm | Type | Key Size | Use Case |
|-----------|------|----------|----------|
| HS256 | Symmetric | 256-bit | Internal services |
| RS256 | Asymmetric | 2048-bit RSA | Public APIs |
| ES256 | Asymmetric | P-256 ECDSA | Mobile, IoT |
| EdDSA | Asymmetric | Ed25519 | Modern systems |

### JWT Validation in Python

```python
import jwt
from jwt import PyJWKClient
from datetime import datetime, timezone

class JWTValidator:
    def __init__(self, issuer: str, audience: str, jwks_url: str):
        self.issuer = issuer
        self.audience = audience
        self.jwk_client = PyJWKClient(jwks_url)

    def validate_token(self, token: str) -> dict:
        """Validate JWT and return claims."""
        try:
            # Fetch signing key from JWKS
            signing_key = self.jwk_client.get_signing_key_from_jwt(token)

            # Decode and validate
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],
                audience=self.audience,
                issuer=self.issuer,
                options={
                    "require": ["exp", "iat", "sub"],
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                }
            )

            return claims

        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.InvalidAudienceError:
            raise AuthenticationError("Invalid audience")
        except jwt.InvalidIssuerError:
            raise AuthenticationError("Invalid issuer")
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {e}")

# Usage
validator = JWTValidator(
    issuer="https://auth.polyvision.io",
    audience="polyvision-api",
    jwks_url="https://auth.polyvision.io/.well-known/jwks.json"
)

claims = validator.validate_token(access_token)
user_id = claims["sub"]
```

### Access Token vs Refresh Token

| Aspect | Access Token | Refresh Token |
|--------|--------------|---------------|
| Lifetime | Short (15-60 min) | Long (days-weeks) |
| Storage | Memory/Cookie | Secure, HTTP-only cookie |
| Contains | User claims, permissions | Token ID only |
| Revocation | Difficult (stateless) | Easy (database lookup) |
| Exposure Risk | Limited window | Requires secure storage |

---

## Session Management / Управление сессиями

### Session Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Browser   │────>│   Gateway    │────>│   Redis     │
│  (Cookie)   │     │   (BFF)      │     │  (Sessions) │
└─────────────┘     └──────────────┘     └─────────────┘
       │                    │                    │
       │  session_id in     │  Lookup session    │
       │  HTTP-only cookie  │  from Redis        │
       │                    │                    │
       │                    │  {                 │
       │                    │    "user_id": ..., │
       │                    │    "org_id": ...,  │
       │                    │    "roles": [...], │
       │                    │    "expires": ...  │
       │                    │  }                 │
```

### Secure Session Cookie Configuration

```python
from datetime import timedelta
from fastapi import Response
import secrets

def create_session(response: Response, user_id: str, org_id: str):
    """Create secure session with HTTP-only cookie."""
    session_id = secrets.token_urlsafe(32)

    # Store session in Redis
    session_data = {
        "user_id": user_id,
        "org_id": org_id,
        "created_at": datetime.utcnow().isoformat(),
        "ip_address": request.client.host,
        "user_agent": request.headers.get("user-agent"),
    }

    redis_client.setex(
        f"session:{session_id}",
        timedelta(hours=24),
        json.dumps(session_data)
    )

    # Set secure cookie
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,      # Prevents JavaScript access
        secure=True,        # HTTPS only
        samesite="lax",     # CSRF protection
        max_age=86400,      # 24 hours
        path="/",
        domain=".polyvision.io"
    )
```

### Session Security Best Practices

1. **Regenerate session ID after login** to prevent session fixation
2. **Bind sessions to user agent and IP** for anomaly detection
3. **Implement absolute and idle timeouts** separately
4. **Store minimal data** in session; fetch permissions on demand
5. **Use secure, random session IDs** (at least 128 bits of entropy)

---

## Implementation Patterns / Паттерны реализации

### Token Refresh Pattern

```python
async def refresh_access_token(refresh_token: str) -> TokenPair:
    """Refresh access token using refresh token."""
    token_record = await db.get_refresh_token(refresh_token)

    if not token_record:
        raise AuthenticationError("Invalid refresh token")

    if token_record.revoked:
        # Potential token theft - revoke all user tokens
        await db.revoke_all_user_tokens(token_record.user_id)
        raise AuthenticationError("Refresh token revoked")

    if token_record.expires_at < datetime.utcnow():
        raise AuthenticationError("Refresh token expired")

    # Rotate refresh token (one-time use)
    await db.revoke_refresh_token(refresh_token)

    # Generate new token pair
    new_access_token = generate_access_token(token_record.user_id)
    new_refresh_token = generate_refresh_token(token_record.user_id)

    await db.store_refresh_token(new_refresh_token, token_record.user_id)

    return TokenPair(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in=900  # 15 minutes
    )
```

### Logout and Token Revocation

```python
async def logout(user_id: str, session_id: str, revoke_all: bool = False):
    """Handle user logout with token revocation."""
    if revoke_all:
        # Revoke all sessions and tokens
        await redis.delete_pattern(f"session:{user_id}:*")
        await db.revoke_all_refresh_tokens(user_id)

        # Increment token version to invalidate all JWTs
        await redis.incr(f"token_version:{user_id}")
    else:
        # Revoke current session only
        await redis.delete(f"session:{session_id}")
```

---

## Security Considerations / Вопросы безопасности

### Common Vulnerabilities

| Vulnerability | Impact | Mitigation |
|---------------|--------|------------|
| Token leakage | Account takeover | Short expiry, secure storage |
| CSRF | Unauthorized actions | SameSite cookies, CSRF tokens |
| XSS | Token theft | HTTP-only cookies, CSP |
| Session fixation | Session hijacking | Regenerate on login |
| Replay attacks | Request duplication | Nonce, timestamp validation |

### Security Checklist

- [ ] Use HTTPS everywhere (HSTS enabled)
- [ ] Implement PKCE for all OAuth flows
- [ ] Store tokens in HTTP-only, Secure cookies
- [ ] Validate all JWT claims (iss, aud, exp, nbf)
- [ ] Implement token rotation for refresh tokens
- [ ] Add rate limiting to authentication endpoints
- [ ] Log all authentication events for auditing
- [ ] Implement account lockout after failed attempts
- [ ] Use constant-time comparison for secrets

---

## Связано с

- [[Authorization]]
- [[Encryption]]
- [[API-Security]]
- [[API-Gateway]]
- [[PV-Security]]

## Ресурсы

1. RFC 6749 - The OAuth 2.0 Authorization Framework: https://datatracker.ietf.org/doc/html/rfc6749
2. RFC 7519 - JSON Web Token (JWT): https://datatracker.ietf.org/doc/html/rfc7519
3. RFC 7636 - Proof Key for Code Exchange (PKCE): https://datatracker.ietf.org/doc/html/rfc7636
4. OpenID Connect Core 1.0: https://openid.net/specs/openid-connect-core-1_0.html
5. OAuth 2.0 Security Best Current Practice: https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics
6. OWASP Session Management Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
7. Auth0 - OAuth 2.0 and OpenID Connect: https://auth0.com/docs/authenticate/protocols
8. Google Identity - OAuth 2.0 for Mobile & Desktop Apps: https://developers.google.com/identity/protocols/oauth2

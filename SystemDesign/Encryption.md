---
tags:
  - system-design
  - security
  - encryption
  - tls
created: 2026-02-17
---

# Шифрование / Encryption: TLS/mTLS, At Rest, Key Management

## Что это

Шифрование — защита данных при передаче (TLS/mTLS) и хранении (AES-256-GCM). Ключевые концепции: AEAD, envelope encryption, key hierarchy (Master Key -> KEK -> DEK), HashiCorp Vault для управления ключами.

---

## Introduction / Введение

Encryption is the cornerstone of data security, protecting information both during transmission (in transit) and while stored (at rest). Modern systems must implement multiple layers of encryption to ensure confidentiality, integrity, and authenticity of data.

Шифрование — краеугольный камень безопасности данных, защищающий информацию как при передаче (в транзите), так и при хранении (в покое). Современные системы должны реализовывать многоуровневое шифрование.

---

## Cryptographic Fundamentals / Основы криптографии

### Symmetric vs Asymmetric Encryption

```
┌─────────────────────────────────────────────────────────────────┐
│              Symmetric Encryption (AES)                          │
├─────────────────────────────────────────────────────────────────┤
│   Plaintext ──[Shared Key]──> Ciphertext ──[Shared Key]──> Plain│
│   + Fast (hardware acceleration)                                │
│   + Efficient for large data                                    │
│   - Key distribution problem                                    │
│   - Scales poorly (n parties = n*(n-1)/2 keys)                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│             Asymmetric Encryption (RSA, ECDSA)                   │
├─────────────────────────────────────────────────────────────────┤
│   Plaintext ──[Public Key]──> Ciphertext ──[Private Key]──> Plain
│   + Solves key distribution                                     │
│   + Digital signatures                                          │
│   + n parties = n key pairs                                     │
│   - Slower than symmetric                                       │
│   - Limited message size                                        │
└─────────────────────────────────────────────────────────────────┘
```

### Modern Algorithm Recommendations

| Use Case | Recommended | Avoid | Notes |
|----------|-------------|-------|-------|
| Symmetric Encryption | AES-256-GCM | DES, 3DES, RC4 | GCM provides AEAD |
| Asymmetric Encryption | RSA-2048+, ECDH P-256 | RSA-1024 | ECDH for key exchange |
| Hashing | SHA-256, SHA-3, BLAKE3 | MD5, SHA-1 | Use HMAC for auth |
| Passwords | Argon2id, bcrypt | SHA-256, MD5 | Memory-hard required |
| Signatures | Ed25519, ECDSA P-256 | RSA-1024, DSA | Ed25519 preferred |

### AEAD (Authenticated Encryption with Associated Data)

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

class AEADEncryption:
    def __init__(self, key: bytes):
        if len(key) != 32:
            raise ValueError("Key must be 256 bits (32 bytes)")
        self.cipher = AESGCM(key)

    def encrypt(self, plaintext: bytes, associated_data: bytes = b"") -> bytes:
        nonce = os.urandom(12)  # 96 bits for GCM
        ciphertext = self.cipher.encrypt(nonce, plaintext, associated_data)
        return nonce + ciphertext  # Prepend nonce

    def decrypt(self, data: bytes, associated_data: bytes = b"") -> bytes:
        nonce = data[:12]
        ciphertext = data[12:]
        return self.cipher.decrypt(nonce, ciphertext, associated_data)

key = os.urandom(32)  # In practice, use KMS
cipher = AEADEncryption(key)
message = b"Sensitive player statistics"
context = b"match_id:finals2024"
encrypted = cipher.encrypt(message, context)
decrypted = cipher.decrypt(encrypted, context)
```

---

## TLS and mTLS / TLS и mTLS

### TLS 1.3 Handshake

```
┌──────────┐                                    ┌──────────┐
│  Client  │                                    │  Server  │
└────┬─────┘                                    └────┬─────┘
     │  1. ClientHello                              │
     │  (supported ciphers, key_share, SNI)         │
     │──────────────────────────────────────────────>│
     │  2. ServerHello + EncryptedExtensions        │
     │  (chosen cipher, key_share, certificate)     │
     │<──────────────────────────────────────────────│
     │  3. Finished (Client)                        │
     │──────────────────────────────────────────────>│
     │  4. Finished (Server)                        │
     │<──────────────────────────────────────────────│
     │  ═══════ Encrypted Application Data ═══════  │

TLS 1.3: 1-RTT handshake (0-RTT with session resumption)
TLS 1.2: 2-RTT handshake
```

### TLS Configuration Best Practices

```nginx
server {
    listen 443 ssl http2;
    server_name api.polyvision.io;

    ssl_certificate /etc/ssl/certs/polyvision.crt;
    ssl_certificate_key /etc/ssl/private/polyvision.key;
    ssl_protocols TLSv1.3 TLSv1.2;
    ssl_ciphers ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers on;
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";
    ssl_stapling on;
    ssl_stapling_verify on;
    ssl_trusted_certificate /etc/ssl/certs/ca-bundle.crt;
    ssl_session_tickets off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
}
```

### Mutual TLS (mTLS)

mTLS requires both client and server to present certificates:

```
┌──────────┐                                    ┌──────────┐
│  Client  │                                    │  Server  │
│ (+ cert) │                                    │ (+ cert) │
└────┬─────┘                                    └────┬─────┘
     │  1. ClientHello                              │
     │──────────────────────────────────────────────>│
     │  2. ServerHello + Server Certificate         │
     │  + CertificateRequest                        │
     │<──────────────────────────────────────────────│
     │  3. Client Certificate + Verify              │
     │──────────────────────────────────────────────>│
     │  4. Server Verifies Client Cert              │
     │  ←─────── Mutual Trust Established ──────────│
```

### Istio mTLS Configuration

```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: polyvision
spec:
  mtls:
    mode: STRICT

---
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: default
  namespace: polyvision
spec:
  host: "*.polyvision.svc.cluster.local"
  trafficPolicy:
    tls:
      mode: ISTIO_MUTUAL
```

### Python mTLS Client

```python
import ssl
import httpx

def create_mtls_client(client_cert, client_key, ca_cert):
    ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ssl_context.load_cert_chain(client_cert, client_key)
    ssl_context.load_verify_locations(ca_cert)
    ssl_context.verify_mode = ssl.CERT_REQUIRED
    return httpx.Client(verify=ssl_context)
```

---

## Encryption at Rest / Шифрование в покое

### Encryption Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                    Encryption at Rest Layers                     │
├─────────────────────────────────────────────────────────────────┤
│  Application Layer          ┌─────────────────────────────────┐ │
│  (Field-level encryption)   │ Encrypt sensitive fields (PII)  │ │
│                             └─────────────────────────────────┘ │
│  Database Layer             ┌─────────────────────────────────┐ │
│  (TDE)                      │ Encrypt tablespaces, columns    │ │
│                             └─────────────────────────────────┘ │
│  Storage Layer              ┌─────────────────────────────────┐ │
│  (Block/Disk encryption)    │ LUKS, dm-crypt, MinIO SSE      │ │
│                             └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Database Encryption Strategies

| Strategy | Scope | Performance | Flexibility |
|----------|-------|-------------|-------------|
| TDE (Tablespace) | Entire database | Minimal impact | Low |
| Column Encryption | Specific columns | Moderate impact | Medium |
| Application-level | Selected fields | High impact | High |
| Tokenization | Sensitive data | Low impact | High |

### Field-Level Encryption (SQLAlchemy)

```python
from cryptography.fernet import Fernet
from sqlalchemy import TypeDecorator, String
import base64

class EncryptedField(TypeDecorator):
    impl = String
    cache_ok = True

    def __init__(self, key: bytes, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fernet = Fernet(key)

    def process_bind_param(self, value, dialect):
        if value is None: return None
        encrypted = self.fernet.encrypt(value.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def process_result_value(self, value, dialect):
        if value is None: return None
        encrypted = base64.urlsafe_b64decode(value.encode())
        return self.fernet.decrypt(encrypted).decode()

class Player(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    email = Column(EncryptedField(encryption_key, length=512))  # PII
    phone = Column(EncryptedField(encryption_key, length=256))  # PII
```

---

## Key Management / Управление ключами

### Key Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                       Key Hierarchy                              │
├─────────────────────────────────────────────────────────────────┤
│                    ┌───────────────────┐                        │
│                    │   Master Key      │ ← HSM-protected        │
│                    │   (KEK Root)      │   Never exported       │
│                    └─────────┬─────────┘                        │
│            ┌─────────────────┼─────────────────┐                │
│     ┌──────┴──────┐   ┌──────┴──────┐   ┌──────┴──────┐        │
│     │  Tenant     │   │  Tenant     │   │  Tenant     │        │
│     │  KEK #1     │   │  KEK #2     │   │  KEK #3     │        │
│     └──────┬──────┘   └──────┬──────┘   └──────┬──────┘        │
│     ┌──────┴──────┐   ┌──────┴──────┐   ┌──────┴──────┐        │
│     │  DEK        │   │  DEK        │   │  DEK        │        │
│     └─────────────┘   └─────────────┘   └─────────────┘        │
│                                                                  │
│  KEK = Key Encryption Key (encrypts other keys)                 │
│  DEK = Data Encryption Key (encrypts actual data)               │
└─────────────────────────────────────────────────────────────────┘
```

### Envelope Encryption Pattern

```python
@dataclass
class EncryptedEnvelope:
    encrypted_dek: bytes
    encrypted_data: bytes
    kek_id: str
    nonce: bytes

class EnvelopeEncryption:
    def __init__(self, kms_client):
        self.kms = kms_client

    def encrypt(self, plaintext: bytes, kek_id: str) -> EncryptedEnvelope:
        dek = os.urandom(32)  # Generate unique DEK
        data_cipher = AESGCM(dek)
        data_nonce = os.urandom(12)
        encrypted_data = data_cipher.encrypt(data_nonce, plaintext, b"")
        encrypted_dek, nonce = self.kms.encrypt_key(dek, kek_id)
        return EncryptedEnvelope(
            encrypted_dek=encrypted_dek,
            encrypted_data=data_nonce + encrypted_data,
            kek_id=kek_id, nonce=nonce)

    def decrypt(self, envelope: EncryptedEnvelope) -> bytes:
        dek = self.kms.decrypt_key(envelope.encrypted_dek, envelope.kek_id, envelope.nonce)
        data_nonce = envelope.encrypted_data[:12]
        ciphertext = envelope.encrypted_data[12:]
        return AESGCM(dek).decrypt(data_nonce, ciphertext, b"")
```

### HashiCorp Vault Integration

```python
import hvac

class VaultKeyManager:
    def __init__(self, vault_addr: str, token: str):
        self.client = hvac.Client(url=vault_addr, token=token)

    def encrypt(self, plaintext: str, key_name: str) -> str:
        response = self.client.secrets.transit.encrypt_data(
            name=key_name, plaintext=self._b64_encode(plaintext))
        return response['data']['ciphertext']

    def decrypt(self, ciphertext: str, key_name: str) -> str:
        response = self.client.secrets.transit.decrypt_data(
            name=key_name, ciphertext=ciphertext)
        return self._b64_decode(response['data']['plaintext'])

    def rotate_key(self, key_name: str):
        self.client.secrets.transit.rotate_key(name=key_name)

    def rewrap_data(self, ciphertext: str, key_name: str) -> str:
        response = self.client.secrets.transit.rewrap_data(
            name=key_name, ciphertext=ciphertext)
        return response['data']['ciphertext']
```

### Key Rotation Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                    Key Rotation Timeline                         │
├─────────────────────────────────────────────────────────────────┤
│  Key v1 ████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░     │
│         ↑ Active        ↑ Decrypt only    ↑ Destroyed           │
│  Key v2        ████████████████████████████░░░░░░░░░░░░░░░░     │
│                ↑ Active                    ↑ Decrypt only       │
│  Key v3                     ████████████████████████████████    │
│                             ↑ Active (current)                  │
│                                                                  │
│  Rotation Policy:                                               │
│  - DEKs: Rotate with each use (one-time keys)                  │
│  - KEKs: Rotate every 90 days                                  │
│  - Master keys: Rotate annually (HSM ceremony)                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Best Practices / Лучшие практики

- [ ] Use TLS 1.3 (or 1.2 minimum) for all external connections
- [ ] Implement mTLS for internal service-to-service communication
- [ ] Encrypt sensitive data at rest using AES-256-GCM
- [ ] Use envelope encryption with proper key hierarchy
- [ ] Store encryption keys in HSM or managed KMS
- [ ] Implement automatic key rotation
- [ ] Never hardcode secrets; use secrets management
- [ ] Enable audit logging for all cryptographic operations
- [ ] Use memory-hard algorithms (Argon2id) for password hashing

---

## Связано с

- [[Authentication]]
- [[API-Security]]
- [[PV-Security]]

## Ресурсы

1. TLS 1.3 RFC 8446: https://datatracker.ietf.org/doc/html/rfc8446
2. NIST Cryptographic Standards: https://csrc.nist.gov/projects/cryptographic-standards-and-guidelines
3. HashiCorp Vault Documentation: https://developer.hashicorp.com/vault/docs
4. AWS KMS Best Practices: https://docs.aws.amazon.com/kms/latest/developerguide/best-practices.html
5. Python Cryptography Library: https://cryptography.io/en/latest/
6. Mozilla SSL Configuration Generator: https://ssl-config.mozilla.org/
7. OWASP Cryptographic Storage Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html

---
tags:
  - kubernetes
  - networking
created: 2026-01-19
---

# Ingress

Kubernetes Ingress — HTTP/HTTPS роутинг снаружи кластера.

## Теория: Что такое Ingress

### Проблема

Service типа `LoadBalancer` работает на L4 (TCP/UDP) — один IP = один сервис. Если в кластере 10 HTTP-приложений, нужно 10 внешних IP.

**Ingress** решает эту проблему на L7 (HTTP/HTTPS):
- Один IP (один LoadBalancer) для множества сервисов
- Роутинг по hostname (`app1.example.com` → Service A, `app2.example.com` → Service B)
- Роутинг по пути (`/api` → backend, `/` → frontend)
- TLS termination (HTTPS снаружи, HTTP внутри кластера)

```
┌─────────────────────────────────────────────────────────────┐
│           Ingress vs LoadBalancer                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Без Ingress (L4):              С Ingress (L7):             │
│                                                              │
│  192.168.20.235 → Service A     192.168.20.235              │
│  192.168.20.236 → Service B       │                         │
│  192.168.20.237 → Service C       ├─ /app1 → Service A     │
│  (3 IP)                           ├─ /app2 → Service B     │
│                                    └─ /app3 → Service C     │
│                                  (1 IP)                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Ingress Controller

Ingress — это только **описание правил** (YAML). Для их исполнения нужен **Ingress Controller** — реальный reverse proxy (nginx, Traefik, HAProxy).

K3s поставляется с **Traefik** как ingress controller по умолчанию.

### Типы роутинга

| Тип | Когда использовать | Пример |
|-----|-------------------|--------|
| **Host-based** | Разные домены | `app.example.com`, `api.example.com` |
| **Path-based** | Один домен, разные пути | `/frontend`, `/api`, `/docs` |
| **TLS termination** | HTTPS наружу | Сертификат на Ingress, HTTP внутри |

## Примеры

### Host-based роутинг

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: example-ingress
spec:
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: my-service
            port:
              number: 80
```

## См. также

- [[Kubernetes]]
- [[K3s]]
- [[Services]]

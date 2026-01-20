---
tags:
  - kubernetes
  - networking
created: 2026-01-19
---

# Ingress

Kubernetes Ingress — HTTP/HTTPS роутинг снаружи кластера.

## Ingress Controller

K3s поставляется с Traefik как ingress controller по умолчанию.

## Пример

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

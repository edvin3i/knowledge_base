---
tags:
  - system-design
  - networking
  - dns
  - cdn
created: 2026-02-17
---

# DNS и сети доставки контента / DNS and CDN

## Что это

DNS (Domain Name System) — иерархическая система преобразования доменных имен в IP-адреса. CDN (Content Delivery Network) — географически распределенная сеть прокси-серверов для быстрой доставки контента. Ключевые темы: GeoDNS, edge caching, HLS/DASH видеостриминг.

---

## DNS Fundamentals / Основы DNS

The Domain Name System (DNS) is a hierarchical distributed database that translates human-readable domain names into IP addresses.

Система доменных имен (DNS) — это иерархическая распределенная база данных, преобразующая читаемые человеком доменные имена в IP-адреса.

### DNS Record Types / Типы DNS-записей

| Record / Запись | Purpose / Назначение | Example / Пример |
|-----------------|---------------------|------------------|
| A | IPv4 address / IPv4 адрес | `example.com → 93.184.216.34` |
| AAAA | IPv6 address / IPv6 адрес | `example.com → 2606:2800:220:1:...` |
| CNAME | Canonical name (alias) / Каноническое имя | `www → example.com` |
| MX | Mail exchange / Почтовый сервер | `mail.example.com` |
| TXT | Text record / Текстовая запись | SPF, DKIM verification |
| NS | Name server / Сервер имен | `ns1.example.com` |
| SOA | Start of Authority / Начало зоны | Zone metadata / Метаданные зоны |

### DNS Hierarchy / Иерархия DNS

```
                    ┌─────────────────┐
                    │   Root Servers  │
                    │  (корневые . )  │
                    │  13 worldwide   │
                    └────────┬────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
    ┌──────────┐      ┌──────────┐      ┌──────────┐
    │   .com   │      │   .org   │      │   .ru    │
    │  (TLD)   │      │  (TLD)   │      │  (TLD)   │
    └────┬─────┘      └────┬─────┘      └────┬─────┘
         │                 │                 │
         ▼                 ▼                 ▼
    ┌──────────┐      ┌──────────┐      ┌──────────┐
    │ example  │      │ example  │      │ example  │
    │   .com   │      │   .org   │      │   .ru    │
    │(authorit)│      │(authorit)│      │(authorit)│
    └──────────┘      └──────────┘      └──────────┘
```

---

## DNS Resolution Process / Процесс разрешения DNS

When you type a URL in your browser, the following process occurs.

Когда вы вводите URL в браузере, происходит следующий процесс.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    DNS Resolution Flow                                   │
│                 (Поток разрешения DNS)                                  │
│                                                                         │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐       │
│  │ Browser  │     │ Resolver │     │ Root DNS │     │ TLD DNS  │       │
│  │(браузер) │     │(резолвер)│     │(корневой)│     │(.com)    │       │
│  └────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘       │
│       │                │                │                │              │
│       │ 1. Query       │                │                │              │
│       │ example.com    │                │                │              │
│       │───────────────>│                │                │              │
│       │                │                │                │              │
│       │                │ 2. Where is    │                │              │
│       │                │ .com?          │                │              │
│       │                │───────────────>│                │              │
│       │                │                │                │              │
│       │                │ 3. .com is at  │                │              │
│       │                │ 192.5.6.30     │                │              │
│       │                │<───────────────│                │              │
│       │                │                │                │              │
│       │                │ 4. Where is    │                │              │
│       │                │ example.com?   │                │              │
│       │                │───────────────────────────────>│              │
│       │                │                │                │              │
│       │                │ 5. example.com │                │              │
│       │                │ NS at ns1...   │                │              │
│       │                │<───────────────────────────────│              │
│       │                │                │                │              │
│       │                │ 6. Query authoritative NS      │              │
│       │                │────────────────────────────────────────────>  │
│       │                │                │                │    ┌─────┐  │
│       │                │ 7. A record: 93.184.216.34     │    │Auth │  │
│       │                │<────────────────────────────────────│ NS  │  │
│       │                │                │                │    └─────┘  │
│       │ 8. IP address  │                │                │              │
│       │ 93.184.216.34  │                │                │              │
│       │<───────────────│                │                │              │
│       │                │                │                │              │
└─────────────────────────────────────────────────────────────────────────┘
```

### DNS Caching Layers / Уровни кеширования DNS

1. **Browser cache** / Кеш браузера (~1-5 minutes)
2. **OS cache** / Кеш ОС (~minutes to hours)
3. **Router cache** / Кеш роутера (varies)
4. **ISP resolver cache** / Кеш резолвера провайдера (TTL-based)

### TTL (Time To Live) / Время жизни записи

```
example.com.    300    IN    A    93.184.216.34
                 ↑
           TTL in seconds (5 minutes)
           TTL в секундах (5 минут)
```

**TTL Strategy / Стратегия TTL:**
- High TTL (86400s): Stable services / Стабильные сервисы
- Low TTL (60-300s): Frequent changes, failover / Частые изменения, отказоустойчивость
- Very low TTL (30s): Active failover / Активное переключение при отказе

---

## GeoDNS / Географический DNS

GeoDNS returns different IP addresses based on the geographic location of the requesting client.

GeoDNS возвращает разные IP-адреса в зависимости от географического местоположения запрашивающего клиента.

```
                         ┌─────────────────────┐
                         │   GeoDNS Server     │
                         │   (сервер GeoDNS)   │
                         └──────────┬──────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         │                          │                          │
         ▼                          ▼                          ▼
   ┌───────────┐             ┌───────────┐             ┌───────────┐
   │  Europe   │             │   Asia    │             │  America  │
   │  (Европа) │             │  (Азия)   │             │ (Америка) │
   │           │             │           │             │           │
   │ Returns:  │             │ Returns:  │             │ Returns:  │
   │ eu.cdn.   │             │ asia.cdn. │             │ us.cdn.   │
   │ example   │             │ example   │             │ example   │
   └───────────┘             └───────────┘             └───────────┘
         │                          │                          │
         ▼                          ▼                          ▼
   ┌───────────┐             ┌───────────┐             ┌───────────┐
   │ Edge PoP  │             │ Edge PoP  │             │ Edge PoP  │
   │ Frankfurt │             │  Tokyo    │             │ New York  │
   └───────────┘             └───────────┘             └───────────┘
```

### GeoDNS Configuration Example / Пример конфигурации GeoDNS

```yaml
# PowerDNS GeoIP backend configuration
# Конфигурация GeoIP для PowerDNS

domains:
  - domain: cdn.example.com
    ttl: 300
    records:
      www:
        - shard: eu
          content: 10.0.1.1
          weight: 100
        - shard: asia
          content: 10.0.2.1
          weight: 100
        - shard: us
          content: 10.0.3.1
          weight: 100

services:
  www:
    default: eu
    mapping:
      EU: eu
      AS: asia
      NA: us
      SA: us
      AF: eu
      OC: asia
```

### Latency-Based Routing / Маршрутизация по задержке

More advanced than GeoDNS, measures actual latency to endpoints.

Более продвинутый подход, чем GeoDNS, измеряющий реальную задержку до конечных точек.

```
Client → DNS Query → Measure latency to all endpoints
                            │
                   ┌────────┼────────┐
                   │        │        │
                   ▼        ▼        ▼
              US: 45ms  EU: 120ms  Asia: 200ms
                   │
                   └─→ Return US endpoint IP
                      (вернуть IP американского эндпоинта)
```

---

## CDN Architecture / Архитектура CDN

A Content Delivery Network (CDN) is a geographically distributed network of proxy servers and data centers.

Сеть доставки контента (CDN) — это географически распределенная сеть прокси-серверов и дата-центров.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CDN Architecture                                 │
│                       (Архитектура CDN)                                 │
│                                                                         │
│                         ┌─────────────────┐                             │
│                         │  Origin Server  │                             │
│                         │ (исходный сервер)│                            │
│                         └────────┬────────┘                             │
│                                  │                                      │
│                    ┌─────────────┼─────────────┐                        │
│                    │             │             │                        │
│                    ▼             ▼             ▼                        │
│             ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│             │  Shield  │  │  Shield  │  │  Shield  │                   │
│             │   (US)   │  │   (EU)   │  │  (Asia)  │                   │
│             │  (щит)   │  │  (щит)   │  │  (щит)   │                   │
│             └────┬─────┘  └────┬─────┘  └────┬─────┘                   │
│                  │             │             │                          │
│       ┌──────────┼─────┐   ┌───┴───┐   ┌─────┼──────────┐              │
│       │          │     │   │       │   │     │          │              │
│       ▼          ▼     ▼   ▼       ▼   ▼     ▼          ▼              │
│    ┌─────┐   ┌─────┐ ┌─────┐  ┌─────┐ ┌─────┐  ┌─────┐ ┌─────┐        │
│    │PoP  │   │PoP  │ │PoP  │  │PoP  │ │PoP  │  │PoP  │ │PoP  │        │
│    │ NY  │   │ LA  │ │Paris│  │Frankf│ │London│ │Tokyo│ │ HK  │        │
│    └──┬──┘   └──┬──┘ └──┬──┘  └──┬──┘ └──┬──┘  └──┬──┘ └──┬──┘        │
│       │         │       │        │       │        │       │            │
│       ▼         ▼       ▼        ▼       ▼        ▼       ▼            │
│     Users     Users   Users    Users   Users    Users   Users          │
│ (пользователи)                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### CDN Components / Компоненты CDN

1. **Origin Server** / Исходный сервер
   - Source of truth for content / Источник истины для контента
   - May be your application server / Может быть вашим сервером приложений

2. **Shield/Mid-tier** / Щит/Средний уровень
   - Reduces origin load / Снижает нагрузку на источник
   - Regional cache aggregation / Региональная агрегация кеша

3. **Edge PoP (Point of Presence)** / Точка присутствия на краю
   - Closest to end users / Ближайшая к конечным пользователям
   - First layer of caching / Первый уровень кеширования

---

## Edge Caching Strategies / Стратегии кеширования на краю

### Cache-Control Headers / Заголовки Cache-Control

```http
# Aggressive caching for static assets
# Агрессивное кеширование для статики
Cache-Control: public, max-age=31536000, immutable

# Moderate caching with revalidation
# Умеренное кеширование с ревалидацией
Cache-Control: public, max-age=3600, must-revalidate

# No caching for dynamic content
# Без кеширования для динамического контента
Cache-Control: private, no-cache, no-store

# Stale-while-revalidate for better UX
# Устаревший-пока-ревалидируется для лучшего UX
Cache-Control: public, max-age=60, stale-while-revalidate=300
```

### Caching Decision Matrix / Матрица решений о кешировании

| Content Type / Тип контента | TTL | Strategy / Стратегия |
|---------------------------|-----|---------------------|
| Static images | 1 year | Immutable, versioned URLs |
| CSS/JS bundles | 1 year | Immutable, content hash |
| Video segments (HLS/DASH) | 1-7 days | Long TTL, no revalidation |
| Manifests (m3u8/mpd) | 1-5 seconds | Very short for live |
| API responses | 0-60 seconds | Vary by auth, short TTL |
| HTML pages | 1-5 minutes | stale-while-revalidate |

### Cache Invalidation / Инвалидация кеша

```
┌─────────────────────────────────────────────────────────────┐
│               Cache Invalidation Methods                     │
│              (Методы инвалидации кеша)                       │
│                                                             │
│  1. Purge by URL                                            │
│     curl -X PURGE https://cdn.example.com/video/123.mp4     │
│                                                             │
│  2. Purge by tag/surrogate key                              │
│     curl -X PURGE -H "Surrogate-Key: match-456"             │
│                                                             │
│  3. Soft purge (mark stale, serve while revalidating)       │
│     curl -X SOFTPURGE ...                                   │
│                                                             │
│  4. URL versioning (cache busting)                          │
│     /video/123.mp4?v=2  →  /video/123.mp4?v=3              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Video Streaming with CDN / Видеостриминг через CDN

### HLS/DASH Segment Caching / Кеширование сегментов HLS/DASH

```
┌─────────────────────────────────────────────────────────────┐
│                  Video Streaming Flow                        │
│               (Поток видеостриминга)                        │
│                                                             │
│  Player                  CDN Edge                 Origin    │
│ (плеер)              (край CDN)              (источник)     │
│    │                       │                       │        │
│    │ 1. GET manifest.m3u8  │                       │        │
│    │──────────────────────>│                       │        │
│    │                       │ cache miss            │        │
│    │                       │──────────────────────>│        │
│    │                       │ manifest + headers    │        │
│    │                       │<──────────────────────│        │
│    │ manifest (TTL=2s)     │                       │        │
│    │<──────────────────────│                       │        │
│    │                       │                       │        │
│    │ 2. GET segment_001.ts │                       │        │
│    │──────────────────────>│                       │        │
│    │                       │ cache miss            │        │
│    │                       │──────────────────────>│        │
│    │                       │ segment + headers     │        │
│    │                       │<──────────────────────│        │
│    │ segment (TTL=1day)    │ (cached)              │        │
│    │<──────────────────────│                       │        │
│    │                       │                       │        │
│    │ 3. GET segment_002.ts │                       │        │
│    │──────────────────────>│                       │        │
│    │ segment (cache hit!)  │                       │        │
│    │<──────────────────────│                       │        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Cache Headers for Video / Заголовки кеширования для видео

```python
# FastAPI example for video streaming headers
# Пример FastAPI для заголовков видеостриминга

from fastapi import FastAPI, Response
from fastapi.responses import FileResponse

app = FastAPI()

@app.get("/live/playlist.m3u8")
async def live_manifest():
    """Live manifest - very short TTL / Живой манифест - очень короткий TTL"""
    response = FileResponse("playlist.m3u8", media_type="application/vnd.apple.mpegurl")
    response.headers["Cache-Control"] = "public, max-age=2, must-revalidate"
    response.headers["CDN-Cache-Control"] = "public, max-age=1"  # Edge-specific
    return response

@app.get("/vod/{match_id}/playlist.m3u8")
async def vod_manifest(match_id: str):
    """VOD manifest - moderate TTL / VOD манифест - умеренный TTL"""
    response = FileResponse(f"manifests/{match_id}.m3u8")
    response.headers["Cache-Control"] = "public, max-age=3600"
    response.headers["Surrogate-Key"] = f"match-{match_id}"  # For purging
    return response

@app.get("/segments/{segment_id}.ts")
async def video_segment(segment_id: str):
    """Video segment - long TTL / Видео сегмент - долгий TTL"""
    response = FileResponse(f"segments/{segment_id}.ts", media_type="video/mp2t")
    response.headers["Cache-Control"] = "public, max-age=604800, immutable"
    return response
```

---

## Implementation Examples / Примеры реализации

### Cloudflare Workers Edge Logic / Логика на краю Cloudflare Workers

```javascript
// Edge-side logic for video streaming
// Логика на стороне края для видеостриминга

addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const url = new URL(request.url)

  // Route video segments to regional origin
  // Маршрутизация видеосегментов к региональному источнику
  if (url.pathname.endsWith('.ts') || url.pathname.endsWith('.m4s')) {
    const region = request.cf?.continent || 'NA'
    const origins = {
      'EU': 'https://eu-origin.example.com',
      'AS': 'https://asia-origin.example.com',
      'NA': 'https://us-origin.example.com'
    }

    const origin = origins[region] || origins['NA']
    const response = await fetch(origin + url.pathname, {
      cf: {
        cacheTtl: 604800,  // 7 days
        cacheEverything: true
      }
    })

    return new Response(response.body, {
      headers: {
        ...response.headers,
        'Cache-Control': 'public, max-age=604800, immutable',
        'X-Edge-Region': region
      }
    })
  }

  // Default handling
  return fetch(request)
}
```

### NGINX CDN Configuration / Конфигурация NGINX для CDN

```nginx
# CDN Edge Server Configuration
# Конфигурация Edge-сервера CDN

proxy_cache_path /var/cache/nginx/video
    levels=1:2
    keys_zone=video_cache:100m
    max_size=50g
    inactive=7d
    use_temp_path=off;

upstream origin_servers {
    server origin1.example.com:8080 backup;
    server origin2.example.com:8080;
    keepalive 32;
}

server {
    listen 443 ssl http2;
    server_name cdn.example.com;

    # Video segments - long cache
    # Видео сегменты - долгий кеш
    location ~ \.(ts|m4s)$ {
        proxy_pass http://origin_servers;
        proxy_cache video_cache;
        proxy_cache_key "$uri";
        proxy_cache_valid 200 7d;
        proxy_cache_use_stale error timeout updating http_500 http_502 http_503;

        add_header X-Cache-Status $upstream_cache_status;
        add_header Cache-Control "public, max-age=604800, immutable";
    }

    # Manifests - short cache
    # Манифесты - короткий кеш
    location ~ \.(m3u8|mpd)$ {
        proxy_pass http://origin_servers;
        proxy_cache video_cache;
        proxy_cache_key "$uri";
        proxy_cache_valid 200 2s;

        add_header Cache-Control "public, max-age=2, must-revalidate";
    }
}
```

---

## Comparison Table / Сравнительная таблица

### CDN Providers / Провайдеры CDN

| Provider / Провайдер | PoPs | Best For / Лучше для | Features / Особенности |
|---------------------|------|---------------------|------------------------|
| Cloudflare | 310+ | General, DDoS protection | Workers, WAF, free tier |
| AWS CloudFront | 450+ | AWS integration | Lambda@Edge, S3 native |
| Fastly | 90+ | Video, real-time purge | VCL, instant purge |
| Akamai | 4000+ | Enterprise, video | Largest network |
| Bunny CDN | 114+ | Cost-effective | Low pricing, simple |

### DNS Strategies / Стратегии DNS

| Strategy / Стратегия | Latency / Задержка | Complexity / Сложность | Use Case / Применение |
|---------------------|-------------------|----------------------|----------------------|
| Simple A record | High / Высокая | Low / Низкая | Single region |
| GeoDNS | Medium / Средняя | Medium / Средняя | Multi-region static |
| Latency-based | Low / Низкая | High / Высокая | Performance critical |
| Anycast | Lowest / Минимальная | High / Высокая | CDN, DNS servers |

---

## Связано с

- [[Load-Balancing]]
- [[API-Gateway]]
- [[PV-Networking]]

## Ресурсы

1. Cloudflare Learning Center - CDN: https://www.cloudflare.com/learning/cdn/what-is-a-cdn/
2. AWS CloudFront Documentation: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/
3. Fastly Documentation: https://docs.fastly.com/
4. RFC 7234 - HTTP Caching: https://tools.ietf.org/html/rfc7234
5. "High Performance Browser Networking" - Ilya Grigorik: https://hpbn.co/
6. DNS-OARC: https://www.dns-oarc.net/
7. PowerDNS Documentation: https://doc.powerdns.com/
8. Apple HLS Authoring Specification: https://developer.apple.com/documentation/http-live-streaming

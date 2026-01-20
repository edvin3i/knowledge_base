---
tags:
  - docker
  - nextcloud
  - portainer
  - self-hosted
created: 2026-01-18
updated: 2026-01-18
---

# Nextcloud AIO

Nextcloud All-in-One — контейнерное решение, автоматически управляющее всеми компонентами.

## Сервер

| Параметр | Значение |
|----------|----------|
| Провайдер | RackNerd |
| Hostname | `racknerd-e57b70` |
| IP | `23.94.44.172` |
| OS | Ubuntu 24.04 |
| RAM | 4 GB |
| Disk | 65 GB |
| Bandwidth | 5.86 TB |
| Virtualization | KVM |

## Docker Compose

```yaml
services:
  nextcloud-aio-mastercontainer:
    image: ghcr.io/nextcloud-releases/all-in-one:latest
    init: true
    restart: always
    container_name: nextcloud-aio-mastercontainer
    volumes:
      - nextcloud_aio_mastercontainer:/mnt/docker-aio-config
      - /var/run/docker.sock:/var/run/docker.sock:ro
    ports:
      - 8080:8080
    environment:
      - APACHE_PORT=11000
      - APACHE_IP_BINDING=0.0.0.0
      - SKIP_DOMAIN_VALIDATION=true

volumes:
  nextcloud_aio_mastercontainer:
```

## Переменные окружения

| Переменная | Значение | Описание |
|------------|----------|----------|
| `APACHE_PORT` | `11000` | Порт Apache для reverse proxy |
| `APACHE_IP_BINDING` | `0.0.0.0` | Биндинг на все интерфейсы |
| `SKIP_DOMAIN_VALIDATION` | `true` | Пропуск проверки домена (NAT loopback) |

## Nginx Proxy Manager

### Proxy Host

| Параметр | Значение |
|----------|----------|
| Domain | `cloud.ibondar.pro` |
| Scheme | `http` |
| Forward Hostname/IP | IP сервера или gateway сети |
| Forward Port | `11000` |
| Websockets Support | Включено |

### SSL

- Request new SSL certificate
- Force SSL: включено
- HTTP/2 Support: включено

### Custom Nginx Configuration

```nginx
client_body_buffer_size 512k;
proxy_read_timeout 86400s;
client_max_body_size 0;
```

## Установка

1. Создать Stack в Portainer с compose выше
2. Открыть `https://IP-сервера:8080`
3. Записать пароль администратора
4. Ввести домен (`cloud.ibondar.pro`)
5. Настроить Proxy Host в NPM
6. Дождаться создания всех контейнеров AIO

## Контейнеры AIO

| Контейнер | Образ | Порты | Описание |
|-----------|-------|-------|----------|
| `nextcloud-aio-mastercontainer` | `all-in-one` | 8080 | Панель управления AIO |
| `nextcloud-aio-apache` | `aio-apache` | 11000 | Веб-сервер |
| `nextcloud-aio-nextcloud` | `aio-nextcloud` | 9000 | Приложение |
| `nextcloud-aio-database` | `aio-postgresql` | 5432 | PostgreSQL |
| `nextcloud-aio-redis` | `aio-redis` | 6379 | Кэш |
| `nextcloud-aio-collabora` | `aio-collabora` | 9980 | Офисный редактор |
| `nextcloud-aio-talk` | `aio-talk` | 3478 (TCP/UDP) | Видеозвонки |
| `nextcloud-aio-notify-push` | `aio-notify-push` | — | Push-уведомления |
| `nextcloud-aio-imaginary` | `aio-imaginary` | — | Обработка изображений |
| `nextcloud-aio-whiteboard` | `aio-whiteboard` | 3002 | Доска для рисования |

## Сети

- AIO создаёт сеть `nextcloud_default` (172.18.0.0/16)
- NPM на сети `extsvcs` (172.19.0.0/16)
- Для связи NPM → Nextcloud использовать gateway `172.18.0.1` или IP хоста

## Управление

- **Панель AIO:** `https://23.94.44.172:8080`
- **Portainer:** `https://odu.ibondar.pro:9443`
- **Stack в Portainer:** `nextcloud`
- **Nextcloud:** `https://cloud.ibondar.pro`

## Troubleshooting

### NAT Loopback не работает

Добавить `SKIP_DOMAIN_VALIDATION=true` в environment.

### 502 Bad Gateway в NPM

- Проверить что `nextcloud-aio-apache` запущен
- Проверить порт 11000
- Использовать IP хоста вместо имени контейнера

## Бэкапы

AIO имеет встроенную систему бэкапов через панель управления (`https://IP:8080`):

- Автоматические бэкапы по расписанию
- Borg Backup для дедупликации
- Возможность восстановления при новой установке

## Ссылки

- [GitHub - Nextcloud AIO](https://github.com/nextcloud/all-in-one)
- [Reverse Proxy Documentation](https://github.com/nextcloud/all-in-one/blob/main/reverse-proxy.md)

## См. также

- [[Docker]]
- [[Nginx-Proxy-Manager]]

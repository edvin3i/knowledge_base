---
tags:
  - docker
  - jitsi
  - portainer
  - self-hosted
created: 2026-01-18
updated: 2026-01-18
---

# Jitsi Meet

Самохостинг видеоконференций на базе Jitsi Meet.

## Сервер

| Параметр | Значение |
|----------|----------|
| Провайдер | RackNerd |
| Hostname | `racknerd-e57b70` |
| IP | `23.94.44.172` |
| OS | Ubuntu 24.04 |

## Docker Compose

```yaml
services:
  web:
    image: jitsi/web:stable-10710
    restart: unless-stopped
    ports:
      - '8443:443'
    volumes:
      - jitsi-web:/config
      - jitsi-transcripts:/usr/share/jitsi-meet/transcripts
    environment:
      - PUBLIC_URL=https://meet.ibondar.pro
      - TZ=Europe/Paris
      - ENABLE_COLIBRI_WEBSOCKET=true
      - ENABLE_XMPP_WEBSOCKET=true
    networks:
      meet.jitsi:

  prosody:
    image: jitsi/prosody:stable-10710
    restart: unless-stopped
    volumes:
      - jitsi-prosody:/config
      - jitsi-prosody-plugins:/prosody-plugins-custom
    environment:
      - PUBLIC_URL=https://meet.ibondar.pro
      - TZ=Europe/Paris
    networks:
      meet.jitsi:
        aliases:
          - xmpp.meet.jitsi

  jicofo:
    image: jitsi/jicofo:stable-10710
    restart: unless-stopped
    volumes:
      - jitsi-jicofo:/config
    environment:
      - TZ=Europe/Paris
    networks:
      meet.jitsi:

  jvb:
    image: jitsi/jvb:stable-10710
    restart: unless-stopped
    ports:
      - '10000:10000/udp'
    volumes:
      - jitsi-jvb:/config
    environment:
      - PUBLIC_URL=https://meet.ibondar.pro
      - JVB_ADVERTISE_IPS=23.94.44.172
      - TZ=Europe/Paris
    networks:
      meet.jitsi:

volumes:
  jitsi-web:
  jitsi-transcripts:
  jitsi-prosody:
  jitsi-prosody-plugins:
  jitsi-jicofo:
  jitsi-jvb:

networks:
  meet.jitsi:
```

## Компоненты

| Контейнер | Образ | Порты | Описание |
|-----------|-------|-------|----------|
| `web` | `jitsi/web` | 8443 | Nginx + веб-интерфейс |
| `prosody` | `jitsi/prosody` | — | XMPP сервер |
| `jicofo` | `jitsi/jicofo` | — | Фокус конференций |
| `jvb` | `jitsi/jvb` | 10000/udp | Видео мост (RTP) |

## Порты

| Порт | Протокол | Назначение |
|------|----------|------------|
| `8443` | TCP | Web UI (для NPM) |
| `10000` | UDP | RTP медиа трафик |

## Nginx Proxy Manager

### Proxy Host

| Параметр | Значение |
|----------|----------|
| Domain | `meet.ibondar.pro` |
| Scheme | `https` |
| Forward Hostname/IP | `23.94.44.172` |
| Forward Port | `8443` |
| Websockets Support | Включено |

### SSL

- Request new SSL certificate
- Force SSL: включено
- HTTP/2 Support: включено

## Firewall

```bash
ufw allow 10000/udp
```

## Управление

- **Jitsi Meet:** `https://meet.ibondar.pro`
- **Portainer:** `https://odu.ibondar.pro:9443`
- **Stack в Portainer:** `jitsi`

## Volumes

Docker Compose создаёт volumes автоматически. Они сохраняются при `docker compose down`, удаляются только с флагом `-v`.

Для внешних volumes добавить `external: true` и создать вручную:

```bash
docker volume create jitsi-web
docker network create meet.jitsi
```

## Дополнительные модули

Опциональные compose файлы:

| Файл | Назначение |
|------|------------|
| `jigasi.yml` | SIP шлюз |
| `jibri.yml` | Запись и стриминг |
| `etherpad.yml` | Совместные документы |
| `whiteboard.yml` | Доска Excalidraw |

## Ссылки

- [Jitsi Handbook](https://jitsi.github.io/handbook/)
- [Docker Guide](https://jitsi.github.io/handbook/docs/devops-guide/devops-guide-docker)
- [GitHub](https://github.com/jitsi/docker-jitsi-meet)

## См. также

- [[Nextcloud-AIO]]
- [[Nginx-Proxy-Manager]]
- [[Docker]]

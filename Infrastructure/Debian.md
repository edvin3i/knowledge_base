---
tags:
  - linux
  - os
created: 2026-01-19
---

# Debian

Linux дистрибутив. Используется на серверах [[K3s]] кластера.

## Версия в кластере

- **Debian 13 (Trixie)** на [[polynode-1]], [[polynode-2]], [[polynode-3]]

## Полезные команды

```bash
# Версия системы
cat /etc/os-release

# Обновление
sudo apt update && sudo apt upgrade -y

# Статус сервисов
systemctl status <service>
```

## Особенности минимальной установки

- `/usr/sbin/` не в PATH — использовать полный путь
- sudo может быть не установлен

## См. также

- [[K3s]]
- [[Homelab]]

---
tags:
  - docker
  - wiki
  - knowledge-base
  - infrastructure
  - vps
created: 2026-02-14
updated: 2026-02-14
---

# Outline

Open-source платформа для управления знаниями и совместной работы команд. Развёрнута на VPS с доменом **kb.aura.ibondar.pro**.

## Теория: Что такое Outline

### Назначение

**Outline** — self-hosted wiki-платформа для создания базы знаний:
- Совместное редактирование в реальном времени (как Google Docs)
- Полная поддержка Markdown
- Структурированная иерархия документов (коллекции → документы)
- Полнотекстовый поиск
- Версионирование документов
- Гибкие права доступа (публичные/приватные документы)
- Интеграция с внешними сервисами (Slack, Figma и т.д.)

### Технологический стек

```yaml
Frontend:  React + TypeScript + MobX + styled-components
Backend:   Node.js + TypeScript + Sequelize ORM
Database:  PostgreSQL
Cache:     Redis
Storage:   S3-compatible (MinIO) или локальное хранилище
Auth:      OAuth 2.0 (Google, Slack, OIDC, Azure AD, Discord)
```

### Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                     Outline Architecture                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Browser ──► Traefik (HTTPS) ──► Outline App (Node.js)         │
│                   │                     │                        │
│                   │                     ├──► PostgreSQL          │
│                   │                     │     (база знаний)      │
│                   │                     │                        │
│                   │                     └──► Redis               │
│                   │                          (cache, sessions)   │
│                   │                                              │
│                   └──► Let's Encrypt (автоматические SSL)        │
│                                                                  │
│   File Storage:                                                  │
│   ┌────────────────────────────────────────────┐                │
│   │ Local: /mnt/.../outline-wiki-storage/      │                │
│   │   ├── postgres/ (база данных)              │                │
│   │   ├── redis/ (кэш)                         │                │
│   │   └── uploads/ (файлы и изображения)       │                │
│   └────────────────────────────────────────────┘                │
│                                                                  │
│   Auth:                                                          │
│   Google OAuth 2.0 ──► Outline ──► Session Management           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Сравнение с другими решениями

| Решение | Тип | Плюсы | Минусы |
|---------|-----|-------|--------|
| **Outline** | Web-based, self-hosted | Совместная работа, красивый UI, real-time | Требует инфраструктуру (PostgreSQL, Redis) |
| **[[Obsidian]]** | Локальный, markdown | Быстрый, offline, граф знаний | Сложная синхронизация для команды |
| **Notion** | SaaS | Простота, интеграции | Закрытый код, зависимость от сервиса |
| **BookStack** | Web-based, self-hosted | Простая установка, иерархия | Нет real-time редактирования |
| **MediaWiki** | Web-based, self-hosted | Проверенное решение | Устаревший UI, сложная настройка |

---

## Практика: Развёртывание

### Репозиторий

**GitHub**: https://github.com/edvin3i/outline-wiki

### Инфраструктура

Развёрнуто на **VPS** с использованием:
- **Docker Compose** для оркестрации контейнеров
- **Traefik** как reverse proxy с автоматическими Let's Encrypt сертификатами
- **Выделенное хранилище**: `/mnt/HC_Volume_102520323/outline-wiki-storage/`

### Структура проекта

```bash
~/outline-wiki/
├── docker-compose.yml    # PostgreSQL + Redis + Outline
├── .env                  # Секреты (не в git!)
├── .env.example          # Шаблон переменных окружения
├── init-storage.sh       # Инициализация хранилища
├── Makefile              # Команды управления
└── README.md             # Документация
```

### Структура хранилища

```bash
/mnt/HC_Volume_102520323/outline-wiki-storage/
├── postgres/    # PostgreSQL database (UID 999)
├── redis/       # Redis cache (UID 999)
└── uploads/     # Uploaded files and images
```

### Первоначальное развёртывание

```bash
# 1. Клонировать репозиторий на VPS
cd ~
git clone git@github.com:edvin3i/outline-wiki.git
cd outline-wiki

# 2. Создать структуру хранилища (требует sudo!)
sudo make init-storage

# 3. Создать .env с автогенерацией секретов
make setup

# 4. Настроить Google OAuth
nano .env
# Добавить:
#   GOOGLE_CLIENT_ID=...
#   GOOGLE_CLIENT_SECRET=...

# 5. Убедиться, что Traefik запущен
cd ~/server-infra
make up
docker network ls | grep tnet-prod

# 6. Запустить Outline
cd ~/outline-wiki
make up

# 7. Проверить логи
make logs
```

### Настройка Google OAuth

1. Перейти в [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Создать проект или выбрать существующий
3. Включить **Google+ API**
4. Создать **OAuth 2.0 Client ID** (тип: Web application)
5. Добавить Authorized redirect URI:
   ```
   https://kb.aura.ibondar.pro/auth/google.callback
   ```
6. Скопировать Client ID и Client Secret в `.env`

### Команды управления

```bash
# Базовые команды
make setup          # Создать .env с автогенерацией секретов
sudo make init-storage  # Инициализировать хранилище (первый раз)
make up             # Запустить все сервисы
make down           # Остановить сервисы
make restart        # Перезапустить
make logs           # Логи в реальном времени
make status         # Статус сервисов

# Управление данными
make clean          # Остановить контейнеры (данные сохранятся)
make clean-data     # Удалить ВСЕ данные ⚠️

# Генерация ключей
make generate-keys  # Сгенерировать SECRET_KEY и UTILS_SECRET
```

### Переменные окружения

Ключевые переменные в `.env`:

```bash
# Автогенерируются через make setup
POSTGRES_PASSWORD=...      # Пароль БД
SECRET_KEY=...             # 256-bit ключ шифрования сессий
UTILS_SECRET=...           # Дополнительный ключ шифрования

# Требуют ручной настройки
GOOGLE_CLIENT_ID=...       # Google OAuth Client ID
GOOGLE_CLIENT_SECRET=...   # Google OAuth Secret

# Опциональные
DEFAULT_LANGUAGE=ru_RU     # Язык интерфейса
WEB_CONCURRENCY=2          # Количество worker процессов
```

---

## Backup и восстановление

### Backup базы данных (SQL dump)

```bash
cd ~/outline-wiki

# Создать дамп PostgreSQL
docker compose -p outline exec postgres \
  pg_dump -U outline outline | \
  gzip > /backups/outline-db-$(date +%Y%m%d).sql.gz
```

### Backup всех данных (полный)

```bash
# Backup всей директории хранилища
sudo tar czf /backups/outline-storage-$(date +%Y%m%d).tar.gz \
  /mnt/HC_Volume_102520323/outline-wiki-storage/
```

### Backup только пользовательских файлов

```bash
# Только uploads (изображения, документы)
sudo tar czf /backups/outline-uploads-$(date +%Y%m%d).tar.gz \
  /mnt/HC_Volume_102520323/outline-wiki-storage/uploads/
```

### Восстановление из backup

```bash
# Восстановление SQL дампа
cat /backups/outline-db-20260214.sql.gz | gunzip | \
  docker compose -p outline exec -T postgres \
  psql -U outline outline

# Восстановление полного хранилища
sudo tar xzf /backups/outline-storage-20260214.tar.gz -C /
```

### Автоматический backup (crontab)

```bash
# Добавить в crontab:
crontab -e

# Бэкап базы данных каждую ночь в 2:00
0 2 * * * cd ~/outline-wiki && docker compose -p outline exec postgres pg_dump -U outline outline | gzip > /backups/outline-db-$(date +\%Y\%m\%d).sql.gz

# Полный бэкап хранилища каждую ночь в 3:00
0 3 * * * tar czf /backups/outline-storage-$(date +\%Y\%m\%d).tar.gz /mnt/HC_Volume_102520323/outline-wiki-storage/
```

---

## Обновление Outline

```bash
cd ~/outline-wiki

# Получить последнюю версию образа
docker compose -p outline pull

# Перезапустить (миграции применятся автоматически)
make restart

# Проверить версию в логах
make logs
```

---

## Troubleshooting

### Сервис не стартует

```bash
# Проверить статус
make status

# Проверить логи
make logs

# Проверить здоровье зависимостей
docker compose -p outline exec postgres pg_isready -U outline
docker compose -p outline exec redis redis-cli ping
```

### Проблемы с миграциями БД

```bash
# Запустить миграции вручную
docker compose -p outline exec outline \
  yarn db:migrate --env=production-ssl-disabled
```

### Google OAuth не работает

1. Проверить redirect URI в Google Console:
   ```
   https://kb.aura.ibondar.pro/auth/google.callback
   ```
2. Убедиться, что Google+ API включен
3. Проверить `GOOGLE_CLIENT_ID` и `GOOGLE_CLIENT_SECRET` в `.env`
4. Перезапустить: `make restart`

### Нет доступа через домен

```bash
# Проверить DNS
nslookup kb.aura.ibondar.pro

# Проверить Traefik
cd ~/server-infra
docker compose -p server-infra ps

# Проверить сеть tnet-prod
docker network ls | grep tnet-prod

# Проверить Traefik dashboard
curl http://localhost:8080/api/http/routers | jq
```

### Проблемы с правами доступа к хранилищу

```bash
# Переинициализировать хранилище
sudo make init-storage

# Проверить права
ls -la /mnt/HC_Volume_102520323/outline-wiki-storage/

# Должно быть:
# postgres/ - 999:999, 700
# redis/    - 999:999, 755
# uploads/  - root:root, 755
```

---

## Мониторинг

### Логи в реальном времени

```bash
# Все сервисы
make logs

# Конкретный сервис
docker compose -p outline logs -f outline
docker compose -p outline logs -f postgres
docker compose -p outline logs -f redis
```

### Использование ресурсов

```bash
# Статистика контейнеров
docker stats --no-stream outline-outline-1 outline-postgres-1 outline-redis-1

# Размер данных
du -sh /mnt/HC_Volume_102520323/outline-wiki-storage/*
```

### Подключение к базе данных

```bash
# PostgreSQL CLI
docker compose -p outline exec postgres \
  psql -U outline outline

# Выполнить SQL запрос
docker compose -p outline exec postgres \
  psql -U outline outline -c "SELECT COUNT(*) FROM documents;"
```

---

## Безопасность

### Генерируемые секреты

- `SECRET_KEY` — 256-bit ключ для шифрования сессий и куки
- `UTILS_SECRET` — Дополнительный ключ для утилит
- `POSTGRES_PASSWORD` — Случайный пароль для PostgreSQL

Генерируются автоматически через `make setup` с использованием OpenSSL.

### HTTPS/TLS

- **Traefik** автоматически выпускает Let's Encrypt сертификаты
- Весь HTTP-трафик редиректится на HTTPS
- Outline работает за Traefik с `FORCE_HTTPS=false` (SSL termination на Traefik)

### OAuth Scopes

Google OAuth запрашивает только:
- Email (для идентификации пользователя)
- Profile name и avatar

### Первый пользователь = Admin

⚠️ **Важно**: Первый вошедший пользователь автоматически получает права администратора!

---

## Полезные ссылки

- **Официальная документация**: https://docs.getoutline.com/
- **GitHub проекта**: https://github.com/outline/outline
- **API документация**: https://www.getoutline.com/developers
- **Community**: https://github.com/outline/outline/discussions
- **Наш репозиторий**: https://github.com/edvin3i/outline-wiki

---

## Связанные документы

- [[Kubernetes]] — для K3s кластера
- [[CVAT]] — другой self-hosted сервис
- [[MinIO]] — S3-совместимое хранилище (можно использовать вместо локального)
- [[Nextcloud-AIO]] — альтернативное решение для файлов и документов

---

## Метрики использования

- **URL**: https://kb.aura.ibondar.pro
- **Домен**: kb.aura.ibondar.pro
- **Аутентификация**: Google OAuth
- **Хранилище**: `/mnt/HC_Volume_102520323/outline-wiki-storage/`
- **Размер файлов**: макс. 25MB на файл
- **Язык интерфейса**: Русский (ru_RU)
- **Инфраструктура**: VPS + Docker Compose + Traefik

---

## История изменений

### 2026-02-14 — Первоначальное развёртывание

- Создан репозиторий: https://github.com/edvin3i/outline-wiki
- Настроен Docker Compose (PostgreSQL + Redis + Outline)
- Интеграция с Traefik (tnet-prod network)
- Настроен Google OAuth
- Локальное хранилище на `/mnt/HC_Volume_102520323/outline-wiki-storage/`
- Автоматическая генерация секретов через Makefile
- Полная документация в README.md

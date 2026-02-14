---
tags:
  - git
  - ssh
  - security
  - deployment
  - infrastructure
created: 2026-02-14
updated: 2026-02-14
---

# Git SSH Deploy Keys

Настройка SSH ключей для безопасного доступа серверов к приватным Git-репозиториям на GitHub/GitLab.

## Теория: Что такое Deploy Key

### Назначение

**Deploy Key** — SSH ключ, предоставляющий доступ только к конкретному репозиторию. Используется для:
- Автоматического деплоя (CI/CD)
- Клонирования приватных репозиториев на серверах
- Доступа без использования личного аккаунта

### Deploy Key vs Personal Access Token

| Параметр | Deploy Key (SSH) | Personal Access Token (HTTPS) |
|----------|------------------|-------------------------------|
| **Область доступа** | Один репозиторий | Все репозитории пользователя |
| **Безопасность** | Высокая (изолированный доступ) | Средняя (широкие права) |
| **Удобство** | Требует настройки SSH | Простая настройка |
| **Ротация** | Ключ не истекает | Требует периодического обновления |
| **Компрометация** | Доступ только к одному репо | Доступ ко всем репо |
| **CI/CD** | Стандарт для production | Подходит для development |

**Рекомендация**: Для production-серверов использовать Deploy Keys с минимальными правами (read-only).

### Типы SSH ключей

| Тип | Безопасность | Совместимость | Размер ключа |
|-----|--------------|---------------|--------------|
| **ED25519** | ⭐⭐⭐⭐⭐ | GitHub, GitLab, современные системы | 256 бит |
| **RSA 4096** | ⭐⭐⭐⭐ | Универсальная совместимость | 4096 бит |
| **ECDSA** | ⭐⭐⭐ | Хорошая, но ED25519 лучше | 256-521 бит |

**Рекомендация**: Использовать **ED25519** — быстрее, безопаснее, короче.

---

## Практика: Настройка Deploy Key

### Шаг 1: Генерация SSH ключа на сервере

```bash
# Подключиться к серверу
ssh user@server-ip

# Сгенерировать ED25519 ключ
ssh-keygen -t ed25519 -C "deploy@project-name" -f ~/.ssh/project-deploy

# Или RSA 4096 для максимальной совместимости
ssh-keygen -t rsa -b 4096 -C "deploy@project-name" -f ~/.ssh/project-deploy
```

**Параметры**:
- `-t ed25519` — тип ключа (алгоритм)
- `-C "deploy@project-name"` — комментарий для идентификации
- `-f ~/.ssh/project-deploy` — путь к файлу ключа

**При запросе passphrase**:
- **Production**: Пустой passphrase (Enter) для автоматизации
- **High-security**: Установить пароль (потребует ввода при каждом git pull)

**Результат**:
```
~/.ssh/project-deploy      — приватный ключ (НИКОГДА НЕ ДЕЛИТЬСЯ!)
~/.ssh/project-deploy.pub  — публичный ключ (для GitHub)
```

### Шаг 2: Установка правильных прав доступа

```bash
# Приватный ключ: только владелец может читать
chmod 600 ~/.ssh/project-deploy

# Публичный ключ: все могут читать
chmod 644 ~/.ssh/project-deploy.pub

# Директория .ssh
chmod 700 ~/.ssh
```

### Шаг 3: Копирование публичного ключа

```bash
# Вывести публичный ключ
cat ~/.ssh/project-deploy.pub
```

Скопируйте **весь вывод** (одна строка, начинается с `ssh-ed25519` или `ssh-rsa`).

### Шаг 4: Добавление Deploy Key на GitHub

1. Откройте репозиторий на GitHub
2. **Settings** → **Deploy keys** → **Add deploy key**
3. Заполните:
   - **Title**: `Server Name - Environment` (например, `VPS Hetzner - Production`)
   - **Key**: вставьте скопированный публичный ключ
   - **Allow write access**:
     - ❌ Для production (только чтение)
     - ✅ Если нужен push с сервера
4. **Add key**

### Шаг 5: Настройка SSH Config

Создайте файл `~/.ssh/config` для упрощения использования:

```bash
nano ~/.ssh/config
```

Добавьте конфигурацию:

```
# Project Deploy Key
Host github.com-project
    HostName github.com
    User git
    IdentityFile ~/.ssh/project-deploy
    IdentitiesOnly yes
```

**Параметры**:
- `Host github.com-project` — алиас для использования в git URL
- `HostName github.com` — реальный хост
- `IdentityFile` — путь к приватному ключу
- `IdentitiesOnly yes` — использовать ТОЛЬКО этот ключ (игнорировать другие)

Установите права:
```bash
chmod 600 ~/.ssh/config
```

### Шаг 6: Тестирование подключения

```bash
# Тест SSH подключения
ssh -T git@github.com-project

# Или без алиаса (явное указание ключа)
ssh -T git@github.com -i ~/.ssh/project-deploy
```

**Ожидаемый результат**:
```
Hi username/repository! You've successfully authenticated, but GitHub does not provide shell access.
```

✅ Если видите это сообщение — настройка успешна!

❌ Если ошибка `Permission denied` — проверьте:
1. Публичный ключ добавлен на GitHub
2. Права на приватный ключ: `chmod 600 ~/.ssh/project-deploy`
3. Путь к ключу в SSH config корректный

### Шаг 7: Клонирование репозитория

#### Вариант A: С алиасом из SSH config

```bash
# Замените github.com на алиас из SSH config
git clone git@github.com-project:username/repository.git ~/project
```

#### Вариант B: Явное указание ключа

```bash
# Через переменную окружения GIT_SSH_COMMAND
GIT_SSH_COMMAND="ssh -i ~/.ssh/project-deploy" \
  git clone git@github.com:username/repository.git ~/project
```

#### Вариант C: Через ssh-agent

```bash
# Запустить ssh-agent
eval "$(ssh-agent -s)"

# Добавить ключ
ssh-add ~/.ssh/project-deploy

# Клонировать стандартно
git clone git@github.com:username/repository.git ~/project
```

### Шаг 8: Переключение существующего репозитория

Если уже клонировали через HTTPS, переключите на SSH:

```bash
cd ~/project

# Посмотреть текущий remote
git remote -v

# Изменить на SSH (с алиасом)
git remote set-url origin git@github.com-project:username/repository.git

# Или без алиаса
git remote set-url origin git@github.com:username/repository.git

# Проверить
git remote -v

# Тест
git pull
```

---

## Работа с несколькими репозиториями

### Вариант 1: Один ключ для всех репозиториев

```bash
# Генерация универсального ключа
ssh-keygen -t ed25519 -C "deploy@vps-hetzner" -f ~/.ssh/vps-deploy

# SSH config
nano ~/.ssh/config
```

```
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/vps-deploy
    IdentitiesOnly yes
```

**Добавьте публичный ключ как Deploy Key в каждый репозиторий.**

### Вариант 2: Отдельный ключ для каждого репозитория

```bash
# Генерация ключей
ssh-keygen -t ed25519 -C "deploy@outline" -f ~/.ssh/outline-deploy
ssh-keygen -t ed25519 -C "deploy@project2" -f ~/.ssh/project2-deploy

# SSH config
nano ~/.ssh/config
```

```
Host github.com-outline
    HostName github.com
    User git
    IdentityFile ~/.ssh/outline-deploy
    IdentitiesOnly yes

Host github.com-project2
    HostName github.com
    User git
    IdentityFile ~/.ssh/project2-deploy
    IdentitiesOnly yes
```

**Клонирование**:
```bash
git clone git@github.com-outline:user/outline-wiki.git
git clone git@github.com-project2:user/project2.git
```

---

## Примеры использования

### Пример 1: Outline Wiki на VPS Hetzner

```bash
# 1. Генерация ключа
ssh-keygen -t ed25519 -C "deploy@outline-wiki-vps" \
  -f ~/.ssh/outline-wiki-deploy

# 2. Копирование публичного ключа
cat ~/.ssh/outline-wiki-deploy.pub

# 3. Добавить на GitHub:
# https://github.com/edvin3i/outline-wiki/settings/keys

# 4. SSH config
cat >> ~/.ssh/config << 'EOF'

Host github.com-outline
    HostName github.com
    User git
    IdentityFile ~/.ssh/outline-wiki-deploy
    IdentitiesOnly yes
EOF

# 5. Права
chmod 600 ~/.ssh/config ~/.ssh/outline-wiki-deploy
chmod 644 ~/.ssh/outline-wiki-deploy.pub

# 6. Тест
ssh -T git@github.com-outline

# 7. Клонирование
git clone git@github.com-outline:edvin3i/outline-wiki.git ~/outline-wiki
```

### Пример 2: CI/CD с GitHub Actions

Для GitHub Actions используйте **Secrets**:

1. Сгенерировать ключ локально
2. Добавить приватный ключ в **Secrets**: `Settings → Secrets → SSH_DEPLOY_KEY`
3. Добавить публичный ключ как **Deploy Key** в целевом репозитории

```yaml
# .github/workflows/deploy.yml
- name: Setup SSH
  uses: webfactory/ssh-agent@v0.7.0
  with:
    ssh-private-key: ${{ secrets.SSH_DEPLOY_KEY }}

- name: Clone private repo
  run: git clone git@github.com:user/private-repo.git
```

---

## Troubleshooting

### Permission denied (publickey)

```bash
# Проверить, что ключ добавлен на GitHub
ssh -T git@github.com -i ~/.ssh/project-deploy

# Проверить права
ls -la ~/.ssh/project-deploy
# Должно быть: -rw------- (600)

# Переустановить права
chmod 600 ~/.ssh/project-deploy
```

### Could not resolve hostname

```bash
# Проверить SSH config
cat ~/.ssh/config

# Проверить алиас
ssh -T git@github.com-project -v
# Verbose mode покажет, какой ключ используется
```

### Key already in use

GitHub не позволяет использовать один публичный ключ в нескольких местах:
- Deploy Key может быть добавлен только в **один** репозиторий
- Если нужен доступ к нескольким репо — используйте разные ключи

### Too many authentication failures

```bash
# SSH пытается использовать все ключи из ~/.ssh/
# Решение: добавьте IdentitiesOnly yes в SSH config

Host github.com-project
    HostName github.com
    User git
    IdentityFile ~/.ssh/project-deploy
    IdentitiesOnly yes  # ← ВАЖНО!
```

### Agent admitted failure to sign

```bash
# Перезапустить ssh-agent
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/project-deploy
```

---

## Безопасность

### Best Practices

✅ **Используйте ED25519** вместо RSA (быстрее, безопаснее)
✅ **Read-only Deploy Keys** для production (без write access)
✅ **Отдельные ключи** для каждого критичного сервиса
✅ **Passphrase** для ключей на локальных машинах
✅ **Регулярная ротация** ключей (раз в год)
✅ **Мониторинг использования** через GitHub Security logs

❌ **Не используйте** один ключ для всех серверов
❌ **Не храните** приватные ключи в репозиториях
❌ **Не шарите** приватные ключи между командой
❌ **Не давайте** write access без необходимости

### Ротация ключей

```bash
# 1. Сгенерировать новый ключ
ssh-keygen -t ed25519 -C "deploy@project-v2" -f ~/.ssh/project-deploy-v2

# 2. Добавить новый ключ на GitHub как второй Deploy Key

# 3. Обновить SSH config
sed -i 's/project-deploy/project-deploy-v2/' ~/.ssh/config

# 4. Тест
ssh -T git@github.com-project
git pull

# 5. Удалить старый ключ с GitHub

# 6. Удалить старый ключ с сервера
rm ~/.ssh/project-deploy ~/.ssh/project-deploy.pub
```

### Проверка активных ключей

```bash
# Все Deploy Keys репозитория (через GitHub CLI)
gh api repos/username/repository/keys

# Или через веб:
# https://github.com/username/repository/settings/keys
```

---

## Альтернативы

### GitHub App (для организаций)

Для организаций с множеством репозиториев:
- Создать GitHub App с нужными правами
- Использовать Installation Token вместо Deploy Keys
- Централизованное управление доступом

### Personal Access Token (HTTPS)

Для development-окружений:

```bash
# Клонирование через HTTPS
git clone https://github.com/username/repository.git

# При запросе пароля:
# Username: username
# Password: ghp_xxxxxxxxxxxx (Personal Access Token)

# Сохранить токен
git config --global credential.helper store
```

**Создать токен**: https://github.com/settings/tokens

---

## См. также

- [[Outline]] — пример использования Deploy Key для VPS
- [GitHub: Deploy Keys](https://docs.github.com/en/developers/overview/managing-deploy-keys)
- [SSH Key Best Practices](https://www.ssh.com/academy/ssh/key)

---

## Полезные команды

```bash
# Список всех SSH ключей
ls -la ~/.ssh/

# Проверить формат ключа
ssh-keygen -l -f ~/.ssh/project-deploy.pub

# Показать fingerprint всех ключей
for key in ~/.ssh/*.pub; do
  echo "$key:"
  ssh-keygen -l -f "$key"
done

# Удалить ключ из ssh-agent
ssh-add -d ~/.ssh/project-deploy

# Показать все ключи в ssh-agent
ssh-add -l

# Очистить все ключи из ssh-agent
ssh-add -D

# Debug SSH подключения
ssh -vvv git@github.com-project
```

---

## Шпаргалка

```bash
# Генерация
ssh-keygen -t ed25519 -C "comment" -f ~/.ssh/key-name

# Права
chmod 600 ~/.ssh/key-name
chmod 644 ~/.ssh/key-name.pub
chmod 600 ~/.ssh/config

# SSH Config
Host github.com-alias
    HostName github.com
    User git
    IdentityFile ~/.ssh/key-name
    IdentitiesOnly yes

# Клонирование
git clone git@github.com-alias:user/repo.git

# Тест
ssh -T git@github.com-alias
```

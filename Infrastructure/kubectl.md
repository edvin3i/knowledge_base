---
tags:
  - kubernetes
  - cli
  - tools
created: 2025-01-16
updated: 2025-01-16
---

# kubectl

CLI для управления Kubernetes кластерами.

## Установка

### Текущая версия

```
Client Version: v1.35.0
Kustomize Version: v5.7.1
```

### Метод установки (ручной)

> **Примечание:** `apt install kubectl` не работает на Ubuntu/Debian без добавления репозитория Kubernetes. Используем ручную установку.

```bash
# Скачать бинарник
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"

# Скачать checksum
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl.sha256"

# Проверить
echo "$(cat kubectl.sha256)  kubectl" | sha256sum --check

# Установить
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Проверить версию
kubectl version --client
```

### Альтернатива: snap

```bash
snap install kubectl --classic
```

## Настройка

### kubeconfig для K3s

На ноде K3s:
```bash
cat /etc/rancher/k3s/k3s.yaml
```

На локальной машине скопировать в `~/.kube/config` и заменить `127.0.0.1` на VIP кластера (`192.168.20.225`).

## Базовые команды

```bash
# Статус нод
kubectl get nodes

# Все поды
kubectl get pods -A

# Поды в namespace
kubectl get pods -n kube-system

# Описание ресурса
kubectl describe pod <pod-name> -n <namespace>

# Логи
kubectl logs <pod-name> -n <namespace>

# Интерактивный shell
kubectl exec -it <pod-name> -n <namespace> -- /bin/sh
```

## kubectl exec

Выполнение команд внутри контейнера (аналог `docker exec`).

### Синтаксис

```bash
kubectl exec -it <pod-name> -- <command>
```

### Флаги

| Флаг | Значение |
|------|----------|
| `-i` | interactive — держать stdin открытым |
| `-t` | tty — выделить псевдо-терминал |
| `-it` | вместе дают интерактивный shell |
| `-n` | namespace |

### Примеры

```bash
# Войти в под по имени
kubectl exec -it nginx-test-66c787d587-6xqlp -- /bin/sh

# Войти в любой под deployment'а
kubectl exec -it deployment/nginx-test -- /bin/sh

# Выполнить команду без входа в shell
kubectl exec nginx-test-66c787d587-6xqlp -- ls /

# В конкретном namespace
kubectl exec -it <pod> -n kube-system -- /bin/sh
```

### Структура имени пода

`nginx-test-66c787d587-6xqlp`:
- `nginx-test` — имя Deployment
- `66c787d587` — хеш ReplicaSet
- `6xqlp` — уникальный суффикс пода

### Shell в разных образах

| Образ | Shell |
|-------|-------|
| alpine | `/bin/sh` |
| ubuntu, debian | `/bin/bash` |
| busybox | `/bin/sh` |

## Полезные алиасы

```bash
# ~/.bashrc или ~/.zshrc
alias k='kubectl'
alias kgp='kubectl get pods'
alias kgn='kubectl get nodes'
alias kga='kubectl get all -A'
```

## См. также

- [[K3s]]
- [[Kubernetes]]
- [[Helm]]
- [[Lens]]

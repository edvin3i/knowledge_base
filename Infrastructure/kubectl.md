---
tags:
  - kubernetes
  - cli
  - tools
created: 2025-01-16
updated: 2026-01-19
---

# kubectl

CLI для управления [[Kubernetes]] кластерами.

## Теория: Как kubectl работает

### Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                        kubectl workflow                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌───────────┐     HTTPS/REST     ┌────────────────┐           │
│   │  kubectl  │ ──────────────────► │   API Server   │           │
│   └───────────┘                     └───────┬────────┘           │
│        │                                    │                    │
│        │ читает                             │ изменяет           │
│        ▼                                    ▼                    │
│   ┌───────────┐                     ┌────────────────┐           │
│   │ kubeconfig│                     │      etcd      │           │
│   │ ~/.kube/  │                     │  (состояние)   │           │
│   │  config   │                     └────────────────┘           │
│   └───────────┘                                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**kubectl** — это просто HTTP клиент к Kubernetes API:
1. Читает kubeconfig для адреса сервера и credentials
2. Отправляет REST запросы (GET, POST, DELETE, PATCH)
3. API Server обрабатывает и сохраняет в etcd

### kubeconfig — файл конфигурации

```yaml
apiVersion: v1
kind: Config

# Кластеры (куда подключаться)
clusters:
- name: k3s-cluster
  cluster:
    server: https://192.168.20.225:6443   # API server URL
    certificate-authority-data: <base64>   # CA сертификат

# Пользователи (как аутентифицироваться)
users:
- name: admin
  user:
    client-certificate-data: <base64>      # Клиентский сертификат
    client-key-data: <base64>              # Приватный ключ

# Контексты (комбинация кластер + пользователь)
contexts:
- name: k3s-admin
  context:
    cluster: k3s-cluster
    user: admin
    namespace: default                     # Namespace по умолчанию

# Текущий контекст
current-context: k3s-admin
```

**Важные поля:**
- `server` — URL API server (в нашем случае VIP)
- `certificate-authority-data` — CA для проверки сервера
- `client-certificate-data` / `client-key-data` — аутентификация клиента

---

## Установка

### Текущая версия

```
Client Version: v1.35.0
Kustomize Version: v5.7.1
```

### Ручная установка

> **Примечание:** `apt install kubectl` требует добавления репозитория Kubernetes.

```bash
# Скачать бинарник
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
```

**Разбор:**
| Элемент | Объяснение |
|---------|------------|
| `curl -LO` | `-L` follow redirects, `-O` сохранить с именем из URL |
| `$(...)` | Command substitution — выполнить и подставить результат |
| `curl -L -s ...stable.txt` | Получить последнюю версию (например "v1.35.0") |
| `linux/amd64` | ОС и архитектура |

```bash
# Скачать checksum
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl.sha256"

# Проверить
echo "$(cat kubectl.sha256)  kubectl" | sha256sum --check
```

**Зачем checksum?**
Проверяет что файл не повреждён при загрузке и не подменён (security).

```bash
# Установить
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
```

**Разбор `install`:**
| Флаг | Значение |
|------|----------|
| `-o root` | Owner = root |
| `-g root` | Group = root |
| `-m 0755` | Mode = rwxr-xr-x (исполняемый) |
| последние аргументы | source destination |

```bash
# Проверить версию
kubectl version --client
```

### Альтернатива: snap

```bash
snap install kubectl --classic
```

`--classic` — полный доступ к системе (без sandboxing).

---

## Настройка

### kubeconfig для K3s

На ноде K3s:
```bash
cat /etc/rancher/k3s/k3s.yaml
```

На локальной машине:
1. Скопировать в `~/.kube/config`
2. Заменить `127.0.0.1` на VIP (`192.168.20.225`)

```bash
# Или через SCP
scp nodeadm@192.168.20.221:/etc/rancher/k3s/k3s.yaml ~/.kube/config
sed -i 's/127.0.0.1/192.168.20.225/' ~/.kube/config
```

### Несколько кластеров

```bash
# Указать другой конфиг
export KUBECONFIG=~/.kube/config-prod

# Или объединить несколько
export KUBECONFIG=~/.kube/config:~/.kube/config-prod

# Переключить контекст
kubectl config use-context k3s-admin
kubectl config use-context prod-cluster

# Список контекстов
kubectl config get-contexts
```

---

## Базовые команды

### Синтаксис

```
kubectl [command] [TYPE] [NAME] [flags]
```

| Элемент | Пример | Описание |
|---------|--------|----------|
| command | get, describe, delete | Что делать |
| TYPE | pods, nodes, services | Тип ресурса |
| NAME | nginx-pod | Имя конкретного ресурса |
| flags | -n kube-system | Опции |

### get — получить список

```bash
# Все ноды
kubectl get nodes

# Все поды во всех namespace
kubectl get pods -A
# или
kubectl get pods --all-namespaces

# Поды в конкретном namespace
kubectl get pods -n kube-system

# Расширенный вывод
kubectl get pods -o wide

# YAML формат
kubectl get pod nginx -o yaml

# JSON формат
kubectl get pod nginx -o json

# Кастомный вывод
kubectl get pods -o custom-columns=NAME:.metadata.name,STATUS:.status.phase
```

**Флаги вывода:**
| Флаг | Формат |
|------|--------|
| `-o wide` | Больше колонок (IP, NODE) |
| `-o yaml` | YAML манифест |
| `-o json` | JSON |
| `-o name` | Только имена |
| `-o jsonpath='{...}'` | Извлечь конкретное поле |

### describe — подробная информация

```bash
kubectl describe node polynode-1
kubectl describe pod nginx -n default
kubectl describe service kubernetes
```

**describe показывает:**
- Spec (желаемое состояние)
- Status (текущее состояние)
- Events (последние события)
- Conditions (условия)

### logs — логи контейнера

```bash
# Логи пода
kubectl logs nginx-pod

# Логи конкретного контейнера (если несколько)
kubectl logs nginx-pod -c nginx

# Последние N строк
kubectl logs nginx-pod --tail=100

# Follow (как tail -f)
kubectl logs nginx-pod -f

# Предыдущий контейнер (после рестарта)
kubectl logs nginx-pod --previous

# По label selector
kubectl logs -l app=nginx
```

### exec — выполнение команд

```bash
# Одна команда
kubectl exec nginx-pod -- ls /

# Интерактивный shell
kubectl exec -it nginx-pod -- /bin/sh
```

**Флаги:**
| Флаг | Назначение |
|------|------------|
| `-i` | stdin открыт (interactive) |
| `-t` | Выделить TTY (терминал) |
| `--` | Разделитель kubectl флагов и команды |

### apply — применить манифест

```bash
# Из файла
kubectl apply -f deployment.yaml

# Из директории
kubectl apply -f ./manifests/

# Из URL
kubectl apply -f https://example.com/manifest.yaml

# Из stdin
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: nginx
spec:
  containers:
  - name: nginx
    image: nginx
EOF
```

**apply vs create:**
- `apply` — декларативный (создаёт или обновляет)
- `create` — императивный (только создаёт, ошибка если существует)

### delete — удаление

```bash
# По имени
kubectl delete pod nginx

# По файлу
kubectl delete -f deployment.yaml

# По label
kubectl delete pods -l app=nginx

# Все поды в namespace
kubectl delete pods --all -n test

# Force delete (stuck pods)
kubectl delete pod nginx --grace-period=0 --force
```

### port-forward — проброс порта

```bash
# Pod -> localhost
kubectl port-forward pod/nginx 8080:80

# Service -> localhost
kubectl port-forward svc/nginx-service 8080:80

# На всех интерфейсах
kubectl port-forward --address 0.0.0.0 pod/nginx 8080:80
```

**Формат:** `localPort:containerPort`

---

## kubectl exec подробно

Выполнение команд внутри контейнера (аналог `docker exec`).

### Примеры

```bash
# Войти в под по имени
kubectl exec -it nginx-test-66c787d587-6xqlp -- /bin/sh

# Войти в любой под deployment'а
kubectl exec -it deployment/nginx-test -- /bin/sh

# Выполнить команду без входа
kubectl exec nginx-pod -- cat /etc/nginx/nginx.conf

# В конкретном namespace
kubectl exec -it nginx -n production -- /bin/bash

# В конкретном контейнере (multi-container pod)
kubectl exec -it mypod -c sidecar -- /bin/sh
```

### Структура имени пода

`nginx-test-66c787d587-6xqlp`:
- `nginx-test` — имя Deployment
- `66c787d587` — хеш ReplicaSet (меняется при обновлении template)
- `6xqlp` — уникальный суффикс пода

### Shell в разных образах

| Образ | Shell | Примечание |
|-------|-------|------------|
| alpine | `/bin/sh` | Минимальный |
| ubuntu, debian | `/bin/bash` | Полный bash |
| busybox | `/bin/sh` | Только sh |
| distroless | нет shell | Нельзя exec |

---

## Полезные команды

### Диагностика

```bash
# Информация о кластере
kubectl cluster-info

# Версии клиента и сервера
kubectl version

# Ресурсы ноды
kubectl top nodes
kubectl top pods

# События в namespace
kubectl get events -n default --sort-by='.lastTimestamp'

# Проблемные поды
kubectl get pods -A | grep -v Running
```

### Работа с ресурсами

```bash
# Создать deployment imperative
kubectl create deployment nginx --image=nginx

# Scale deployment
kubectl scale deployment nginx --replicas=3

# Обновить образ
kubectl set image deployment/nginx nginx=nginx:1.25

# Rollout статус
kubectl rollout status deployment/nginx

# Откатить
kubectl rollout undo deployment/nginx

# История rollout
kubectl rollout history deployment/nginx
```

### Label и Annotation

```bash
# Добавить label
kubectl label node polydev-desktop gpu=true

# Удалить label
kubectl label node polydev-desktop gpu-

# Показать labels
kubectl get nodes --show-labels

# Фильтр по label
kubectl get pods -l app=nginx
kubectl get pods -l 'app in (nginx, apache)'
```

---

## Полезные алиасы

```bash
# ~/.bashrc или ~/.zshrc
alias k='kubectl'
alias kgp='kubectl get pods'
alias kgn='kubectl get nodes'
alias kga='kubectl get all -A'
alias kd='kubectl describe'
alias kl='kubectl logs'
alias ke='kubectl exec -it'
alias kaf='kubectl apply -f'
alias kdf='kubectl delete -f'
```

### Автодополнение

```bash
# Bash
source <(kubectl completion bash)
echo 'source <(kubectl completion bash)' >> ~/.bashrc

# Zsh
source <(kubectl completion zsh)
echo 'source <(kubectl completion zsh)' >> ~/.zshrc
```

---

## JSONPath примеры

```bash
# IP всех подов
kubectl get pods -o jsonpath='{.items[*].status.podIP}'

# Имена всех нод
kubectl get nodes -o jsonpath='{.items[*].metadata.name}'

# GPU на ноде
kubectl get node polydev-desktop -o jsonpath='{.status.allocatable.nvidia\.com/gpu}'

# Все images
kubectl get pods -o jsonpath='{.items[*].spec.containers[*].image}' | tr ' ' '\n' | sort -u
```

---

## См. также

- [[K3s]]
- [[Kubernetes]]
- [[Helm]]
- [[Lens]]
- [kubectl Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)

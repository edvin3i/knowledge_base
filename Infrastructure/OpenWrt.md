---
tags:
  - networking
  - linux
  - router
created: 2025-01-15
---

# OpenWrt

Открытая прошивка для роутеров и сетевых устройств.

## Мои устройства

- [[Cisco Meraki MX64]] — управляемый свитч в [[Homelab]]

## Особенности SNAPSHOT

В OpenWrt SNAPSHOT используется **apk** (как в Alpine), а не opkg.

| Действие | Команда |
|----------|---------|
| Обновить списки | `apk update` |
| Установить пакет | `apk add <pkg>` |
| Удалить пакет | `apk del <pkg>` |
| Обновить всё | `apk upgrade` |
| Поиск | `apk search <pkg>` |

## Базовая настройка

### LuCI (веб-интерфейс)

```bash
apk update
apk add luci
```

### Пароль root

```bash
passwd
```

## UCI — конфигурация

```bash
uci show network           # Показать конфиг сети
uci set network.lan.ipaddr='192.168.1.1'
uci commit                 # Сохранить
service network restart    # Применить
```

## Полезные команды

```bash
logread          # Системный лог
dmesg            # Лог ядра
ifconfig         # Интерфейсы
```

## Ресурсы

- [OpenWrt Documentation](https://openwrt.org/docs/start)
- [Table of Hardware](https://openwrt.org/toh/start)

## См. также

- [[Cisco Meraki MX64]]
- [[Networking]]

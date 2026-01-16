---
tags:
  - hardware
  - networking
  - homelab
created: 2025-01-15
---

# Cisco Meraki MX64

Межсетевой экран на базе Broadcom BCM5862x (ARM). Использую с [[OpenWrt]] как управляемый свитч.

## Характеристики

- **SoC:** Broadcom BCM5862x (ARM)
- **Порты:** 5x GbE (1 WAN + 4 LAN)
- **Консоль:** Serial 115200 8N1

## Моя конфигурация

- **IP:** `192.168.20.222`
- **Роль:** Управляемый свитч
- **Прошивка:** [[OpenWrt]] SNAPSHOT
- **Gateway:** `192.168.20.254`
- **DNS:** Cloudflare Family (`1.1.1.3`)

## Версии SoC

Важно для установки — нужен правильный образ.

Проверка в U-Boot:
```
u-boot> md 0x18000000 1
```

| Значение | Версия |
|----------|--------|
| `0x3F00xxxx` — `0x3F03xxxx` | MX64 **A0** |
| `0x3F04xxxx` и выше | Обычный **MX64** |

Мой: `0x3F05xxxx` — обычный MX64.

## Документация

- [[MX64 - Установка OpenWrt]] — пошаговая инструкция
- [[MX64 - U-Boot команды]] — справочник

## Ресурсы

- [OpenWrt Table of Hardware](https://openwrt.org/toh/meraki/mx64)
- [PR #3996](https://github.com/openwrt/openwrt/pull/3996) — исходный PR

## См. также

- [[OpenWrt]]
- [[Homelab]]

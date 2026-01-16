---
tags:
  - openwrt
  - howto
  - hardware
created: 2025-01-15
---

# MX64 — Установка OpenWrt

Пошаговая инструкция по установке [[OpenWrt]] на [[Cisco Meraki MX64]].

## Требования

- USB флешка (FAT32)
- Serial-кабель (115200 8N1)
- initramfs образ (нужно собрать самому — нет в официальных снапшотах)
- sysupgrade образ (есть в снапшотах)

## Сборка initramfs

```bash
git clone https://github.com/openwrt/openwrt.git
cd openwrt
./scripts/feeds update -a
./scripts/feeds install -a
make menuconfig
```

В menuconfig:
- Target System → Broadcom BCM47xx/53xx (ARM)
- Subtarget → Generic (NAND)
- Target Profile → Cisco Meraki MX64
- Target Images → **[*] ramdisk** ← обязательно!

```bash
make -j$(nproc)
```

Результат: `bin/targets/bcm53xx/generic/openwrt-bcm53xx-generic-meraki_mx64-initramfs.bin`

## Скачивание sysupgrade

```bash
# Для обычного MX64
wget https://downloads.openwrt.org/snapshots/targets/bcm53xx/generic/openwrt-bcm53xx-generic-meraki_mx64-squashfs.sysupgrade.bin

# Для MX64 A0
wget https://downloads.openwrt.org/snapshots/targets/bcm53xx/generic/openwrt-bcm53xx-generic-meraki_mx64_a0-squashfs.sysupgrade.bin
```

---

## Установка через Serial

### Шаг 1: Загрузка в U-Boot

1. Подключить serial (115200 8N1)
2. Включить устройство
3. Прервать автозагрузку (любая клавиша)

### Шаг 2: Загрузка с USB

```
u-boot> usb start
u-boot> fatls usb 0:1
u-boot> fatload usb 0:1 0x90000000 openwrt-bcm53xx-generic-meraki_mx64-initramfs.bin
u-boot> bootbk 0x90000000 kernel
```

> **Важно:** Используется `bootbk`, не `bootm` — формат Meraki bootkernel.

### Шаг 3: Загрузка sysupgrade

После загрузки initramfs, в консоли:

```bash
cd /tmp
wget http://192.168.1.2:8080/openwrt-bcm53xx-generic-meraki_mx64-squashfs.sysupgrade.bin
```

На компьютере:
```bash
python3 -m http.server 8080
```

> SCP не работает в initramfs — нет sftp-server.

### Шаг 4: Установка

```bash
sysupgrade -n /tmp/openwrt-...-sysupgrade.bin
```

`-n` — не сохранять конфигурацию (первая установка).

---

## Настройка как свитч

Все 5 портов как LAN, без роутинга:

```bash
# Отключить DHCP
uci set dhcp.lan.ignore='1'

# Статический IP
uci set network.lan.proto='static'
uci set network.lan.ipaddr='192.168.20.222'
uci set network.lan.netmask='255.255.255.0'
uci set network.lan.gateway='192.168.20.254'
uci add_list network.lan.dns='1.1.1.3'

# WAN порт в bridge
uci add_list network.@device[0].ports='wan'

# Удалить WAN интерфейсы
uci delete network.wan
uci delete network.wan6

uci commit
reboot
```

---

## Troubleshooting

### Wrong Image Format for bootm command

**Решение:** Использовать `bootbk` вместо `bootm`

### Bad Linux ARM zImage magic!

**Решение:** Образ в формате Meraki bootkernel — `bootbk`

### Device not supported by this image

**Решение:** Принудительная установка:
```bash
sysupgrade -n -F /tmp/...-sysupgrade.bin
```

### SCP не работает

**Решение:** wget или netcat:
```bash
# На MX64
nc -l -p 1234 > /tmp/sysupgrade.bin
# На ПК
nc 192.168.1.1 1234 < файл.bin
```

## См. также

- [[Cisco Meraki MX64]]
- [[OpenWrt]]
- [[MX64 - U-Boot команды]]

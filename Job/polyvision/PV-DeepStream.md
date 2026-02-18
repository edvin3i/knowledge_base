---
tags:
  - polyvision
  - deepstream
  - nvidia
  - edge
  - gpu
  - version-analysis
created: 2026-02-18
---

# Polyvision — DeepStream версии и калибровка камер

## Что это

Анализ версий NVIDIA DeepStream SDK для платформы [[Polyvision]]. Dual-platform: **Jetson Orin NX 16GB** (edge, live) + **RTX A6000 48GB** (server, offline). Решение: version lock на **DeepStream 7.1** (ADR-003).

## Матрица версий DeepStream

| | **DS 7.0** (May 2024) | **DS 7.1** (Sep 2024) | **DS 8.0** (Late 2025) |
|---|---|---|---|
| **RTX A6000 (Ampere SM 8.6)** | Yes | Yes | Yes |
| **Jetson Orin NX** | Yes (JP 6.0) | Yes (JP 6.1/6.2) | **Нет** |
| **Jetson Thor** | Нет | Нет | Yes |
| **Ubuntu** | 22.04 | 22.04 | **24.04** |
| **CUDA** | 12.2 | 12.6 | 12.8 |
| **TensorRT** | 8.6 | 10.3 | 10.9 |
| **NVIDIA Driver** | 535.x | ~545.x | 570.x |
| **Triton** | — | 24.08 | 25.03 |
| **GStreamer** | 1.20.x | 1.20.x | 1.20.x |

### DS 7.0 → 7.1 изменения

- Triton updated to 24.08
- Service Maker expanded to Python (ранее только C++)
- Новый `nvds_measure_buffer_latency()` API
- Improved ReID accuracy in tracker
- Enhanced Single-View 3D Tracking
- `get_request_pad()` deprecated → `request_pad_simple()`
- Gray 16 LE pixel format support
- SBSA (server-side ARM) support

### DS 7.1 → 8.0 изменения

**Новое:**
- Blackwell GPU + Jetson Thor support
- **MaskTracker** — трекер на базе SAM2 (Segment Anything Model 2), pixel-level сегментация
- **Multi-View 3D Tracking (MV3DT)** — 3D позиционирование из нескольких камер + pose estimation
- REST API для `nvdsanalytics` и `nvtracker` (hot-reload конфигов)
- CUDA-enabled OpenCV в dsexample
- Open-sourced: nvll_osd, smart record, image encode/decode plugins

**Удалено:**
- TensorFlow, UFF, Caffe model backends
- Audio support (ASR, TTS plugins)
- INT8 calibration для legacy TAO models
- Graph Composer (deprecated, последний релиз)

**Breaking changes:**
- Ubuntu 22.04 → **24.04** (обязательно)
- CUDA 12.6 → 12.8
- NVIDIA Driver → 570.x
- **Orin NX НЕ поддерживается** — NVIDIA: *"currently no plan to support Orin platforms with DS 8.0"*

## Почему DS 7.1 (Version Lock)

### Критическая проблема: Orin NX заблокирован

DeepStream 8.0 поддерживает только Jetson Thor. Наш edge-устройство (Orin NX 16GB) не может перейти на 8.0. Поддержка Orin NX ожидается с **JetPack 7.2** (Q2 2026), но соответствующая версия DeepStream не анонсирована.

### Split (server 8.0 + edge 7.1) — отвергнут

| За | Против |
|----|--------|
| MaskTracker (SAM2) на сервере | Два окружения, двойное CI |
| TensorRT 10.9 | Расхождение API |
| Pose estimation | `sports-analytics-core` требует version parity |
|  | Ubuntu 22.04 → 24.04 на сервере |

### Что из DS 8.0 было бы полезно для Polyvision

| Фича | Полезность | Применимость |
|-------|-----------|-------------|
| **MaskTracker (SAM2)** | Средняя | Pixel-level сегментация игроков → точные heatmaps, VCam framing. Но SAM2 доступен standalone через PyTorch |
| **MV3DT (3D Tracking)** | Низкая | Требует multi-camera extrinsics. Наш dual-camera rig с baseline ~20-30 см даёт ΔZ ≈ 2.8м на 50м — неприемлемо |
| **Pose Estimation** | Средняя | Ориентация тела, техника бега. Premium-аналитика Phase 3+ |
| **TensorRT 10.9** | Низкая | ~10-15% throughput. Offline pipeline — скорость не критична |
| **REST API** | Низкая | Batch processing — нет нужды в hot-reload |

### Решение

**DS 7.1 для обеих платформ.** Точка пересмотра: **Q3 2026** (после выхода JetPack 7.2).

## Container Images (NGC)

| Tag | Назначение | Arch |
|-----|-----------|------|
| `7.1-triton-multiarch` | Runtime + Triton | x86 + Jetson Orin |
| `7.1-gc-triton-devel` | Dev SDK + Graph Composer + Triton | x86 |
| `7.1-samples-multiarch` | Runtime + samples | x86 + Jetson Orin |
| `7.1-triton-arm-sbsa` | Triton для ARM серверов | ARM SBSA |

## Калибровка камер: 2D Homography vs 3D

### Текущий подход: 2D Homography + LUT

**Цель**: Склеить два 2D изображения в панораму.

```
CAM_LEFT → feature matching → Homography H (3×3) → LUT → CUDA kernel → Панорама
CAM_RIGHT ↗
```

**Что знает**: как пиксели левой камеры соответствуют пикселям правой.
**Что НЕ знает**: положение камер в мире, фокусное расстояние, реальные расстояния.

**LUT файлы (6 шт):**
- `lut_left_x`, `lut_left_y` — координаты ремаппинга левой камеры
- `lut_right_x`, `lut_right_y` — координаты ремаппинга правой камеры
- `weight_left`, `weight_right` — веса блендинга в зоне перекрытия

### 3D Calibration (что нужно для MV3DT)

**Intrinsics (внутренние параметры)** — свойства самой камеры:
```
K = [fx  0  cx]    fx, fy — фокусное расстояние (pixels)
    [0  fy  cy]    cx, cy — principal point (центр)
    [0   0   1]
+ коэффициенты дисторсии (k1, k2, p1, p2, k3)
```
*Получение*: ChArUco/checkerboard из ~20 ракурсов → `cv2.calibrateCamera()`

**Extrinsics (внешние параметры)** — положение камеры в мире:
```
R (3×3 rotation) + t (3×1 translation)
"Камера на высоте 15м, наклон 25°, смотрит на центр поля"
```
*Получение*: Известные точки поля (углы штрафной, центр) → `cv2.solvePnP()`

**Триангуляция**:
```
CAM_LEFT (K₁,R₁,t₁)     CAM_RIGHT (K₂,R₂,t₂)
         \                     /
          \ луч 1     луч 2  /
           \               /
            \ ● ИГРОК    /
             (X,Y,Z)   /
              метры   /
```

### Почему 3D НЕ работает для нашего rig

```
Ошибка глубины ∝ distance² / (focal_length × baseline)

baseline = 0.3m (камеры рядом на одном кронштейне)
distance = 50m (до середины поля)
focal_length = 3000px (приблизительно для IMX678)

ΔZ ≈ 50² / (3000 × 0.3) ≈ 2.8м ← НЕПРИЕМЛЕМО
```

MV3DT рассчитан на стадионные установки с 8-12 камерами на **разных** позициях (baseline = метры).

### Решение: Field Homography

Промежуточный подход — проекция на плоскость поля (не требует DS 8.0):

```
Step 1: Stitching LUT (one-time per rig)
  Feature matching → Homography → LUT → Calibration Registry

Step 2: Field Homography (per installation site)
  4+ точек на панораме ↔ реальные координаты на поле (FIFA: 105m × 68m)
  → cv2.findHomography() → матрица H_field

Step 3: Detection → Field coordinates
  bbox center (pixels) × H_field → position (meters)
  Допущение: Z ≈ 0 (объекты на земле)
```

| Метрика | 2D Homography (пиксели) | + Field Homography (метры) | Full 3D |
|---------|------------------------|---------------------------|---------|
| Позиция на поле | Пиксели панорамы | **Метры (X, Y)** | Метры (X, Y, Z) |
| Пробег | Приблизительно | **Точно** | Точно |
| Скорость | Относительная | **м/с, км/ч** | м/с, км/ч |
| Heatmaps | Пиксельная сетка | **Реальные зоны поля** | Реальные зоны |
| Offside | Искажение перспективы | Приемлемо | Точно |
| Высота мяча | Невозможно | Невозможно | Возможно |

## Timeline

| Когда | Действие |
|-------|---------|
| Сейчас (Phase 1-2) | DS 7.1 everywhere, stitching LUT |
| Phase 2.5 | Добавить field homography → координаты в метрах |
| **Q3 2026** | Пересмотр: JetPack 7.2 + DS 8.x для Orin NX? |
| Phase 3 | SAM2 standalone (без DS 8.0), pose estimation research |

## TODO

- [ ] Проверить `get_request_pad()` в pipeline — deprecated в DS 7.1, заменить на `request_pad_simple()`
- [ ] Зафиксировать JetPack 6.2 как minor upgrade для edge (community-verified)
- [ ] Реализовать field homography (4+ контрольных точки на поле)
- [ ] Добавить field_homography matrix в Calibration Registry (ADR-014)

## Связано с

- [[Polyvision]] — обзор проекта
- [[Polyvision-Stack]] — стек технологий
- [[PV-Storage]] — ClickHouse хранит детекции в пиксельных координатах

## Ресурсы

- [DeepStream 8.0 Release Notes](https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_Release_notes.html)
- [DeepStream 7.1 Release Notes (PDF)](https://docs.nvidia.com/metropolis/deepstream/DeepStream_7.1_Release_Notes.pdf)
- [NGC DeepStream Container Tags](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/deepstream/tags)
- [DS 8.0 Orin Support — NVIDIA Forum](https://forums.developer.nvidia.com/t/deepstream-8-0-support-for-jetson-orin-agx/350772)
- [OpenCV Camera Calibration](https://docs.opencv.org/4.x/dc/dbb/tutorial_py_calibration.html)
- Репозиторий: `~/Expirements/polyvision/docs/decisions.md` (ADR-003, ADR-024)

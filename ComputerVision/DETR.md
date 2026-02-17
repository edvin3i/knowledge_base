---
tags:
  - cv
  - detection
  - segmentation
  - transformer
created: 2026-02-17
---

# DETR

Семейство Detection Transformer — детекторы на основе трансформеров, альтернатива YOLO.

## Теория: Что такое DETR

### Назначение

**DETR (DEtection TRansformer)** — подход к детекции объектов через архитектуру трансформера:
- End-to-end детекция без NMS (Non-Maximum Suppression)
- Бинарное сопоставление (Hungarian matching) вместо anchor-boxes
- Глобальный контекст через self-attention

### Эволюция

```
DETR (2020) → Deformable DETR → RT-DETR (2023) → RT-DETRv2 → RT-DETRv4 (2024)
                                                    RF-DETR (2025, Roboflow)
                                                    D-FINE (2024)
```

### DETR vs YOLO: ключевые отличия

| Аспект | YOLO | DETR |
|--------|------|------|
| Архитектура | CNN-based | Transformer-based |
| Post-processing | NMS | End-to-end |
| Anchors | Anchor-free (v8+) | Query-based |
| Малые объекты | Хуже | Лучше (deformable attention) |
| Скорость обучения | Быстрее | Медленнее (больше эпох) |

## RT-DETR / RT-DETRv2

### Что это

**RT-DETR (Real-Time DEtection TRansformer)** — первый DETR-детектор реального времени от Baidu.

### Ключевые особенности

- **Hybrid encoder**: CNN backbone + transformer encoder для баланса скорости и точности
- **Selective Multi-Scale Sampling**: эффективная обработка объектов разных размеров
- **End-to-end**: не требует NMS post-processing

### RT-DETRv2

- Достигает **55.3% AP на COCO**, превосходя YOLOv8 по FPS и точности
- Особенно эффективен для объектов разного размера

## RT-DETRv4

### Что это

Последняя версия RT-DETR с дистилляцией знаний от Vision Foundation Models.

### Ключевые улучшения

- **Knowledge Distillation** от DINOv3 для улучшения лёгких моделей
- До **57.0 AP** (модель-X) на COCO
- **78 FPS** на GPU T4
- Гибкий фреймворк для адаптации к разным задачам

## RF-DETR (Roboflow)

### Что это

**RF-DETR** — архитектура от Roboflow на основе DINOv2 backbone. Поддерживает детекцию и instance segmentation.

### Ключевые результаты

| Модель | COCO AP₅₀ | Latency |
|--------|-----------|---------|
| RF-DETR-B | 67.6 | 2.3 ms |
| RF-DETR-L | 78.5 | 17.2 ms |

### Особенности

- Deformable attention для эффективной обработки
- Apache 2.0 лицензия (base модели)
- Тонкая настройка через Roboflow API
- Instance segmentation (голова вдохновлена MaskDINO)

### Использование

```python
from rfdetr import RFDETRBase

model = RFDETRBase()

# Fine-tune
model.train(dataset_dir="dataset/", epochs=50, lr=1e-4)

# Predict
detections = model.predict("image.jpg", threshold=0.5)
```

## D-FINE

### Что это

**D-FINE** — DETR-детектор с Fine-grained Distribution Refinement (FDR) и Global Optimal Localization Self-Distillation (GO-LSD).

### Ключевая идея

Переопределяет регрессию bbox как уточнение распределения вероятностей, а не прямое предсказание координат. Самодистилляция без дополнительных затрат при инференсе.

### Результаты

| Модель | COCO AP | FPS |
|--------|---------|-----|
| D-FINE-N | 42.8 | 472 |
| D-FINE-X | 55.8 | — |

## Связано с
- [[YOLO]] — CNN-based альтернатива
- [[SAM]] — foundation model для сегментации
- [[NVIDIA_Inference]] — деплой через TensorRT/DeepStream

## Ресурсы
- [RF-DETR GitHub](https://github.com/roboflow/rf-detr)
- [RT-DETRv4 GitHub](https://github.com/RT-DETRs/RT-DETRv4)
- [D-FINE GitHub](https://github.com/Peterande/D-FINE)
- [RF-DETR Segmentation (Roboflow)](https://roboflow.com/model/rf-detr-segmentation)
- [RT-DETRv2 vs YOLO (Labellerr)](https://www.labellerr.com/blog/rt-detrv2-beats-yolo-full-comparison-tutorial/)
- [RF-DETR: внутренний взгляд (AIHubNews)](https://aihubnews.ru/articles/rf-detr-vnutrenniy-vzglyad-na-real-taym-detektor)

---
tags:
  - cv
  - detection
  - segmentation
  - yolo
created: 2026-02-17
---

# YOLO

Семейство моделей You Only Look Once — одноэтапные детекторы/сегментаторы реального времени.

## Теория: Что такое YOLO

### Назначение

**YOLO (You Only Look Once)** — семейство моделей для задач компьютерного зрения:
- Object detection (bounding boxes)
- Instance segmentation
- Pose estimation
- Oriented bounding boxes (OBB)
- Classification

### Ключевая идея

В отличие от двухстадийных детекторов (R-CNN), YOLO обрабатывает изображение **за один проход** (single-stage):

```
Input Image → Backbone (feature extraction) → Neck (feature fusion) → Head (predictions)
```

Это обеспечивает высокую скорость при приемлемой точности.

### Эволюция архитектуры

| Версия | Год | Backbone | Ключевое нововведение |
|--------|-----|----------|----------------------|
| YOLOv5 | 2020 | CSPDarknet | PyTorch, удобный API |
| YOLOv8 | 2023 | CSPDarknet mod | Anchor-free, decoupled head |
| YOLOv11 | 2024 | C3k2 + SPPF | Улучшенная feature extraction, выше accuracy/speed |

## YOLOv8

### Архитектура

**Backbone**: модифицированный CSPDarknet с C2f-блоками для извлечения признаков на разных масштабах.

**Neck**: FPN + PAN — объединение признаков разного разрешения для обнаружения объектов разных размеров.

**Head**: decoupled (раздельный) — отдельные ветки для классификации и регрессии bbox. Anchor-free подход: предсказывает центр объекта и расстояния до краёв bbox.

### Размеры моделей

| Модель | Params | mAP₅₀₋₉₅ (COCO) | Скорость |
|--------|--------|-------------------|----------|
| YOLOv8n | 3.2M | 37.3 | Самая быстрая |
| YOLOv8s | 11.2M | 44.9 | |
| YOLOv8m | 25.9M | 50.2 | |
| YOLOv8l | 43.7M | 52.9 | |
| YOLOv8x | 68.2M | 53.9 | Самая точная |

### Повышение точности YOLOv8

Трюк с Pose-моделью для малых объектов:
1. Преобразовать координаты центров bbox в ключевые точки (keypoints)
2. Обучить как Pose-задачу с весами box/dfl = 0.01
3. Конвертировать обратно в Detection-формат без потери скорости

Результат: **mAP50 с 44.8 до 50.6** на TT100K (малые объекты).

## YOLOv11

### Архитектура

- **C3k2-блоки**: улучшенное извлечение признаков
- **SPPF (Spatial Pyramid Pooling - Fast)**: эффективное агрегирование контекста
- Улучшенная скорость и точность по сравнению с YOLOv8

## Использование

```python
from ultralytics import YOLO

# Detection
model = YOLO("yolo11n.pt")
results = model("image.jpg")

# Segmentation
model = YOLO("yolo11n-seg.pt")
results = model("image.jpg")

# Training
model.train(data="dataset.yaml", epochs=100, imgsz=640)

# Export to ONNX/TensorRT
model.export(format="onnx")
```

## Связано с
- [[DETR]] — альтернативные transformer-детекторы
- [[SAM]] — foundation model для сегментации
- [[NVIDIA_Inference]] — деплой на Jetson/DeepStream
- [[CVAT]] — разметка данных для обучения

## Ресурсы
- [YOLOv8 Explained (Medium)](https://medium.com/@melissa.colin/yolov8-explained-understanding-object-detection-from-scratch-763479652312)
- [YOLOv11 Explained (Medium)](https://medium.com/@nikhil-rao-20/yolov11-explained-next-level-object-detection-with-enhanced-speed-and-accuracy-2dbe2d376f71)
- [Увеличение точности YOLOv8](https://y-t-g.github.io/tutorials/yolov8-increase-accuracy/)
- [Ultralytics Docs](https://docs.ultralytics.com/)

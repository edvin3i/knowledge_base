---
tags:
  - cv
  - inference
  - nvidia
  - jetson
  - edge
created: 2026-02-17
---

# NVIDIA Inference

Инструменты NVIDIA для деплоя моделей компьютерного зрения: DeepStream, Jetson, NGC.

## DeepStream SDK

### Что это

**NVIDIA DeepStream SDK** — платформа для создания конвейеров видеоаналитики с GPU-ускорением:
- Обработка множества видеопотоков одновременно
- Интеграция с TensorRT для оптимизации моделей
- GStreamer-based пайплайны

### DeepStream-Yolo

Конфигурация DeepStream для моделей YOLO. Поддерживает:
- YOLOv5, YOLOv8, YOLOv10, YOLO11
- RT-DETR, YOLO-NAS и другие архитектуры
- Автоматическая конвертация в TensorRT

```
Video Input → DeepStream → TensorRT (YOLO/DETR) → Bounding Boxes → Output/Analytics
```

## NVIDIA Jetson

### Многокамерные пайплайны

Пакет **jetmulticam** для обработки нескольких видеопотоков на Jetson:
- Использует DLA (Deep Learning Accelerator) + GPU
- CPU < 20% при обработке 3 потоков с 2 моделями одновременно
- Предобученные модели: PeopleNet, DashCamNet
- Подходит для робототехники и видеоаналитики

### Jetson для детекции инструментов

Пример real-time детекции и трекинга инструментов:
- YOLO + DeepStream на Jetson Xavier NX / Orin
- Трекинг объектов в реальном времени
- Применение в промышленности и мастерских

## NGC Catalog

### Что это

**NVIDIA NGC Catalog** — платформа с GPU-оптимизированным ПО:
- Контейнеры (PyTorch, TensorFlow, TensorRT)
- Предобученные модели
- Рецепты обучения
- LTSB-версии с 36-месячной поддержкой

### Полезные ресурсы NGC

- **TensorRT** контейнер — для оптимизации моделей
- **DeepStream** контейнер — для видеоаналитики
- **TAO Toolkit** — transfer learning для моделей NVIDIA
- Предобученные модели: PeopleNet, TrafficCamNet, DashCamNet

## Связано с
- [[YOLO]] — модели для деплоя
- [[DETR]] — transformer-модели для деплоя
- [[K3s_GPU-Support]] — GPU в кластере

## Ресурсы
- [DeepStream-Yolo GitHub](https://github.com/marcoslucianops/DeepStream-Yolo)
- [Multi-Camera Pipelines with Jetson (NVIDIA Blog)](https://developer.nvidia.com/blog/implementing-real-time-multi-camera-pipelines-with-nvidia-jetson/)
- [Real-time Tool Detection with Jetson (Reddit)](https://www.reddit.com/r/computervision/comments/1h9dpfe/realtime_tool_detection_and_tracking_with_jetson/)
- [NVIDIA NGC Catalog](https://catalog.ngc.nvidia.com/)

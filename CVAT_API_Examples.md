---
tags:
  - cvat
  - api
  - scripts
  - automation
created: 2026-02-14
---
# CVAT API - Примеры и скрипты

Коллекция скриптов для автоматизации работы с CVAT через API.

## Скрипты

### 1. create_cvat_task_validation.py

**Назначение**: Создание задачи в CVAT из изображений в MinIO Cloud Storage.

**Параметры** (в начале файла):
```python
PROJECT_ID = 4  # Polyvision 4 classes
CLOUD_STORAGE_ID = 4  # MinIO Datasets
MINIO_PREFIX = "path/to/images"
TASK_NAME = "task-name"
SUBSET = "validation"  # или "train", "test"
IMAGE_QUALITY = 100  # 1-100
SEGMENT_SIZE = 1000  # изображений на job
```

**Использование**:
```bash
python3 create_cvat_task_validation.py
```

**Что делает**:
1. Получает список файлов из MinIO через CVAT API
2. Создаёт задачу с указанными параметрами
3. Привязывает файлы из Cloud Storage
4. Ожидает завершения обработки
5. Выводит результат

---

### 2. update_task_subset.py

**Назначение**: Обновление subset для существующих задач.

**Использование**:
```bash
# Перенести задачи в train subset
python3 update_task_subset.py train 19 17 14

# Перенести задачу в validation subset
python3 update_task_subset.py validation 20

# Перенести задачи в test subset
python3 update_task_subset.py test 21 22
```

**Что делает**:
- Обновляет параметр `subset` для указанных задач через PATCH запрос
- Выводит результат для каждой задачи

---

### 3. show_project_subsets.py

**Назначение**: Показать распределение задач по subsets в проекте.

**Использование**:
```bash
python3 show_project_subsets.py
```

**Вывод**:
```
======================================================================
📊 Polyvision 4 classes - Dataset Split
======================================================================

Total frames: 12,649

📁 Subset: train
   Tasks: 3
   Frames: 10,261
   Percentage: 81.1%
   Details:
     • #19: Vincennes-Athletic-small_2026-02-10_201919 (3930 frames)
     • #17: Stade-de-la-Tour-aux-Parachutes_2026-02-10_155217 (4836 frames)
     • #14: Polyvision 4cls - full dataset v1.1.6 (1495 frames)

📁 Subset: validation
   Tasks: 1
   Frames: 2,388
   Percentage: 18.9%
   Details:
     • #20: nrt_Parc-Omnisport-Suzanne-Lenglen_2026-02-14_validation (2388 frames)

======================================================================
```

---

## Примеры CVAT API запросов

### Получить список задач проекта

```bash
curl -s -H "Authorization: Token $CVAT_TOKEN" \
  "http://192.168.20.235/api/tasks?project_id=4" | python3 -m json.tool
```

### Получить информацию о задаче

```bash
curl -s -H "Authorization: Token $CVAT_TOKEN" \
  "http://192.168.20.235/api/tasks/20" | python3 -m json.tool
```

### Обновить subset задачи

```bash
curl -s -X PATCH \
  -H "Authorization: Token $CVAT_TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Organization: Ploycube" \
  "http://192.168.20.235/api/tasks/20" \
  -d '{"subset": "validation"}' | python3 -m json.tool
```

### Получить список файлов из Cloud Storage

```bash
curl -s -H "Authorization: Token $CVAT_TOKEN" \
  "http://192.168.20.235/api/cloudstorages/4/content-v2?prefix=path/to/images/" | \
  python3 -m json.tool
```

### Создать задачу с Cloud Storage

**Шаг 1: Создать задачу (метаданные)**
```bash
TASK_ID=$(curl -s -X POST "http://192.168.20.235/api/tasks" \
  -H "Authorization: Token $CVAT_TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Organization: Ploycube" \
  -d '{
    "name": "Task Name",
    "project_id": 4,
    "subset": "train",
    "segment_size": 1000,
    "source_storage": {
      "location": "cloud_storage",
      "cloud_storage_id": 4
    },
    "target_storage": {
      "location": "cloud_storage",
      "cloud_storage_id": 3
    }
  }' | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")

echo "Created task #${TASK_ID}"
```

**Шаг 2: Привязать файлы из Cloud Storage**
```bash
curl -s -X POST "http://192.168.20.235/api/tasks/${TASK_ID}/data" \
  -H "Authorization: Token $CVAT_TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Organization: Ploycube" \
  -d '{
    "cloud_storage_id": 4,
    "server_files": [
      "path/to/image1.jpg",
      "path/to/image2.jpg"
    ],
    "image_quality": 100,
    "use_zip_chunks": true,
    "use_cache": true,
    "sorting_method": "natural"
  }'
```

**Шаг 3: Проверить статус обработки**
```bash
RQ_ID="action=create&target=task&target_id=${TASK_ID}"
curl -s "http://192.168.20.235/api/requests/${RQ_ID}" \
  -H "Authorization: Token $CVAT_TOKEN" | python3 -m json.tool
```

---

## Важные параметры

### Subset
- `train` - тренировочный набор
- `validation` - валидационный набор
- `test` - тестовый набор
- Пустая строка или `null` - без subset

### Image Quality
- `1-100` - качество сжатия JPEG chunks
- `70` - default (рекомендуется для большинства задач)
- `100` - максимальное качество (внимание: сильно нагружает KVRocks PVC!)

### Segment Size
- Количество изображений в одном Job
- Рекомендуется: `1000` для обычных изображений
- Влияет на количество Jobs в задаче

### Cloud Storage ID
- `3` - MinIO CVAT Internal (для экспортов/бэкапов)
- `4` - MinIO Datasets (для исходных данных)

**ВАЖНО**: `cloud_storage_id` нужно указывать **и в задаче** (`source_storage`), **и в data payload**!

---

## Troubleshooting

### Ошибка "No such file or directory"
- Проверьте, что `cloud_storage_id` указан в data payload
- Проверьте пути в `server_files` (без имени bucket, только путь внутри bucket)

### Задача создалась, но нет изображений
- Проверьте статус обработки через `/api/requests/{rq_id}`
- Проверьте, что файлы существуют в Cloud Storage

### KVRocks PVC заполнен
- При `image_quality=100` chunks кэшируются без сжатия
- Решение: используйте `image_quality=70` или очистите KVRocks cache

---

## См. также

- [[CVAT]] - основная документация по CVAT
- [[MinIO]] - документация по MinIO
- [CVAT API Documentation](http://192.168.20.235/api/docs)

#!/usr/bin/env python3
"""
Создание задачи в CVAT из изображений в MinIO Cloud Storage.

Проект: Polyvision 4 classes
Subset: validation
Источник: datasets bucket, prefix nrt_Parc-Omnisport-Suzanne-Lenglen_2026-02-14_024152/images/
Качество: 100%
Размер пачки: 1000 изображений
"""

import requests
import json
from typing import List

# Конфигурация
CVAT_URL = "http://192.168.20.235"
CVAT_TOKEN = "8f5b243c8de90f8e895b50c716e77aad03b79ab1"
PROJECT_ID = 4  # Polyvision 4 classes
CLOUD_STORAGE_ID = 4  # MinIO Datasets
TARGET_STORAGE_ID = 3  # MinIO CVAT Internal (для экспортов)
ORGANIZATION = "Ploycube"

# Параметры задачи
MINIO_PREFIX = "nrt_Parc-Omnisport-Suzanne-Lenglen_2026-02-14_024152/images"
TASK_NAME = "nrt_Parc-Omnisport-Suzanne-Lenglen_2026-02-14_validation"
SUBSET = "validation"
IMAGE_QUALITY = 100
SEGMENT_SIZE = 1000

# Headers для всех запросов
HEADERS = {
    "Authorization": f"Token {CVAT_TOKEN}",
    "Content-Type": "application/json",
    "X-Organization": ORGANIZATION
}


def get_files_from_cloud_storage(prefix: str) -> List[str]:
    """Получить список файлов из Cloud Storage через CVAT API."""
    print(f"📂 Получение списка файлов из cloud storage (prefix: {prefix})...")

    all_files = []
    next_token = None

    while True:
        url = f"{CVAT_URL}/api/cloudstorages/{CLOUD_STORAGE_ID}/content-v2"
        params = {"prefix": f"{prefix}/"}
        if next_token:
            params["next_token"] = next_token

        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        data = response.json()

        # Отфильтровать только файлы (не директории)
        files = [
            f"{prefix}/{item['name']}"
            for item in data.get("content", [])
            if item.get("type") == "REG" and item.get("mime_type") in ["image"]
        ]
        all_files.extend(files)

        # Пагинация
        next_token = data.get("next")
        if not next_token:
            break

    print(f"✓ Найдено {len(all_files)} изображений")
    return sorted(all_files)


def create_task(name: str, subset: str) -> int:
    """Создать задачу в CVAT (шаг 1)."""
    print(f"\n📝 Создание задачи '{name}' в проекте {PROJECT_ID}...")

    payload = {
        "name": name,
        "project_id": PROJECT_ID,
        "subset": subset,
        "segment_size": SEGMENT_SIZE,
        "source_storage": {
            "location": "cloud_storage",
            "cloud_storage_id": CLOUD_STORAGE_ID
        },
        "target_storage": {
            "location": "cloud_storage",
            "cloud_storage_id": TARGET_STORAGE_ID
        }
    }

    response = requests.post(
        f"{CVAT_URL}/api/tasks",
        headers=HEADERS,
        json=payload
    )
    response.raise_for_status()
    task = response.json()
    task_id = task["id"]

    print(f"✓ Задача создана: ID={task_id}, URL={CVAT_URL}/tasks/{task_id}")
    return task_id


def attach_data_to_task(task_id: int, server_files: List[str]) -> str:
    """Привязать файлы из Cloud Storage к задаче (шаг 2)."""
    print(f"\n📦 Привязка {len(server_files)} файлов к задаче {task_id}...")

    payload = {
        "cloud_storage_id": CLOUD_STORAGE_ID,
        "server_files": server_files,
        "image_quality": IMAGE_QUALITY,
        "use_zip_chunks": True,
        "use_cache": True,
        "sorting_method": "natural"
    }

    response = requests.post(
        f"{CVAT_URL}/api/tasks/{task_id}/data",
        headers=HEADERS,
        json=payload
    )
    response.raise_for_status()
    result = response.json()
    rq_id = result.get("rq_id")

    print(f"✓ Данные отправлены на обработку: request_id={rq_id}")
    return rq_id


def wait_for_task_processing(rq_id: str, timeout: int = 600) -> bool:
    """Ожидать завершения обработки задачи."""
    import time

    print(f"\n⏳ Ожидание обработки задачи (timeout={timeout}s)...")

    start_time = time.time()
    while time.time() - start_time < timeout:
        response = requests.get(
            f"{CVAT_URL}/api/requests/{rq_id}",
            headers=HEADERS
        )
        response.raise_for_status()
        request_info = response.json()

        status = request_info.get("status")
        message = request_info.get("message", "")

        if status == "finished":
            print(f"✓ Обработка завершена успешно!")
            return True
        elif status == "failed":
            print(f"✗ Ошибка обработки: {message}")
            return False

        # Прогресс
        print(f"  Status: {status} - {message}", end="\r")
        time.sleep(2)

    print(f"\n✗ Timeout: обработка не завершилась за {timeout}s")
    return False


def main():
    """Основная функция."""
    print("=" * 70)
    print("🚀 Создание задачи CVAT из MinIO Cloud Storage")
    print("=" * 70)
    print(f"  Проект: Polyvision 4 classes (ID={PROJECT_ID})")
    print(f"  Subset: {SUBSET}")
    print(f"  Prefix: {MINIO_PREFIX}")
    print(f"  Качество: {IMAGE_QUALITY}%")
    print(f"  Размер пачки: {SEGMENT_SIZE} изображений")
    print("=" * 70)

    try:
        # Шаг 1: Получить список файлов из Cloud Storage
        files = get_files_from_cloud_storage(MINIO_PREFIX)

        if not files:
            print("✗ Не найдено ни одного файла в указанной директории!")
            return 1

        print(f"\n📊 Статистика:")
        print(f"  - Всего изображений: {len(files)}")
        print(f"  - Jobs (по {SEGMENT_SIZE} изобр.): {(len(files) + SEGMENT_SIZE - 1) // SEGMENT_SIZE}")

        # Показать несколько примеров файлов
        print(f"\n  Примеры файлов:")
        for f in files[:3]:
            print(f"    • {f}")
        if len(files) > 3:
            print(f"    ... и ещё {len(files) - 3} файлов")

        # Автоматическое подтверждение
        print(f"\n✅ Продолжаем создание задачи...")

        # Шаг 2: Создать задачу
        task_id = create_task(TASK_NAME, SUBSET)

        # Шаг 3: Привязать файлы
        rq_id = attach_data_to_task(task_id, files)

        # Шаг 4: Дождаться обработки
        success = wait_for_task_processing(rq_id)

        if success:
            print("\n" + "=" * 70)
            print("✅ УСПЕХ!")
            print("=" * 70)
            print(f"  Задача: {TASK_NAME}")
            print(f"  ID: {task_id}")
            print(f"  URL: {CVAT_URL}/tasks/{task_id}")
            print(f"  Subset: {SUBSET}")
            print(f"  Изображений: {len(files)}")
            print("=" * 70)
            return 0
        else:
            print(f"\n❌ ОШИБКА: задача создана (ID={task_id}), но обработка не завершилась успешно")
            print(f"   Проверьте задачу вручную: {CVAT_URL}/tasks/{task_id}")
            return 1

    except requests.HTTPError as e:
        print(f"\n❌ HTTP Ошибка: {e}")
        print(f"   Response: {e.response.text}")
        return 1
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())

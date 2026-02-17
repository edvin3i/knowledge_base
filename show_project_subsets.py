#!/usr/bin/env python3
"""Показать распределение задач по subsets в проекте CVAT."""

import requests
import sys

CVAT_URL = "http://192.168.20.235"
CVAT_TOKEN = "8f5b243c8de90f8e895b50c716e77aad03b79ab1"
PROJECT_ID = 4  # Polyvision 4 classes

headers = {
    "Authorization": f"Token {CVAT_TOKEN}",
    "X-Organization": "Ploycube"
}

# Получить все задачи проекта
response = requests.get(
    f"{CVAT_URL}/api/tasks",
    headers=headers,
    params={"project_id": PROJECT_ID}
)
response.raise_for_status()
tasks = response.json()["results"]

# Группировка по subset
subsets = {}
for task in tasks:
    subset = task.get("subset") or "(not set)"
    if subset not in subsets:
        subsets[subset] = {"count": 0, "frames": 0, "tasks": []}

    subsets[subset]["count"] += 1
    subsets[subset]["frames"] += task["size"]
    subsets[subset]["tasks"].append(
        f"#{task['id']}: {task['name']} ({task['size']} frames)"
    )

# Вывод статистики
print("=" * 70)
print("📊 Polyvision 4 classes - Dataset Split")
print("=" * 70)

total_frames = sum(s["frames"] for s in subsets.values())
print(f"\nTotal frames: {total_frames:,}")
print()

for subset, data in sorted(subsets.items()):
    print(f"📁 Subset: {subset}")
    print(f"   Tasks: {data['count']}")
    print(f"   Frames: {data['frames']:,}")
    print(f"   Percentage: {data['frames']/total_frames*100:.1f}%")
    print(f"   Details:")
    for task in data["tasks"]:
        print(f"     • {task}")
    print()

print("=" * 70)

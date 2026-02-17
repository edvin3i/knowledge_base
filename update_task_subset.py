#!/usr/bin/env python3
"""
Обновить subset для задач в CVAT.

Usage:
  python3 update_task_subset.py <subset> <task_id> [task_id ...]

Examples:
  python3 update_task_subset.py train 19 17 14
  python3 update_task_subset.py validation 20
  python3 update_task_subset.py test 21 22
"""

import requests
import sys

CVAT_URL = "http://192.168.20.235"
CVAT_TOKEN = "8f5b243c8de90f8e895b50c716e77aad03b79ab1"
ORGANIZATION = "Ploycube"

headers = {
    "Authorization": f"Token {CVAT_TOKEN}",
    "Content-Type": "application/json",
    "X-Organization": ORGANIZATION
}


def update_task_subset(task_id: int, subset: str) -> dict:
    """Обновить subset задачи."""
    response = requests.patch(
        f"{CVAT_URL}/api/tasks/{task_id}",
        headers=headers,
        json={"subset": subset}
    )
    response.raise_for_status()
    return response.json()


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1

    subset = sys.argv[1]
    task_ids = [int(tid) for tid in sys.argv[2:]]

    print("=" * 70)
    print(f"🔄 Updating subset to '{subset}' for {len(task_ids)} task(s)")
    print("=" * 70)
    print()

    success = 0
    failed = 0

    for task_id in task_ids:
        try:
            task = update_task_subset(task_id, subset)
            print(f"✓ Task #{task['id']}: {task['name']}")
            print(f"  Subset: {task['subset']}")
            print(f"  Size: {task['size']} frames")
            print()
            success += 1
        except requests.HTTPError as e:
            print(f"✗ Task #{task_id}: Error - {e}")
            print(f"  Response: {e.response.text}")
            print()
            failed += 1

    print("=" * 70)
    print(f"✅ Updated: {success}")
    if failed:
        print(f"❌ Failed: {failed}")
    print("=" * 70)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())

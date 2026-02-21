"""
asyncio vs sync 벤치마크.

CPU-bound 작업에서 asyncio의 한계를 숫자로 확인한다.

사용법 (컨테이너 내부):
    cd /app/src && uv run python -m scripts.bench_async
"""

import asyncio
import os
import sys

from processor.sync_runner import run as sync_run
from processor.async_runner import run as async_run
from processor.async_runner import run_with_executor
from utility.timer import timer

FIXTURES_DIR = "/app/tests/fixtures"


async def main():
    image_paths = [
        os.path.join(FIXTURES_DIR, f)
        for f in sorted(os.listdir(FIXTURES_DIR))
        if f.endswith((".jpg", ".jpeg", ".png"))
    ]

    if not image_paths:
        print(f"No images found in {FIXTURES_DIR}")
        sys.exit(1)

    count = 10
    images = (image_paths * ((count // len(image_paths)) + 1))[:count]
    operation = "blur"
    params = {"radius": 10}

    print(f"Images: {count}장 | Operation: {operation}")
    print(f"GIL enabled: {sys._is_gil_enabled()}")
    print("=" * 55)

    # 1. sync (기준선)
    with timer("sync") as t:
        sync_run(images, operation, params)
    sync_time = t.elapsed
    print(f"  {'sync':<30s}  {t.elapsed:.3f}s  (기준선)")

    # 2. asyncio (순수 async — CPU-bound에선 순차와 동일)
    with timer("async (pure)") as t:
        await async_run(images, operation, params)
    print(f"  {'async (pure)':<30s}  {t.elapsed:.3f}s  ({t.elapsed / sync_time:.2f}x)")

    # 3. asyncio + run_in_executor (스레드풀 위임)
    for workers in [1, 2, 4]:
        label = f"async + executor ({workers} workers)"
        with timer(label) as t:
            await run_with_executor(images, operation, params, workers=workers)
        print(f"  {label:<30s}  {t.elapsed:.3f}s  ({t.elapsed / sync_time:.2f}x)")

    print("=" * 55)
    print()
    print("분석:")
    print("  - async (pure): sync와 거의 동일 → CPU-bound에선 asyncio가 무의미")
    if sys._is_gil_enabled():
        print("  - executor: GIL=1이라 스레드를 늘려도 개선 없음")
    else:
        print("  - executor: GIL=0이라 worker 수에 비례해서 빨라짐")


if __name__ == "__main__":
    asyncio.run(main())

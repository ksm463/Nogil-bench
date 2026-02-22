"""
동시성 3가지 비교 벤치마크: sync vs threading vs multiprocessing.

Day 4 핵심 실험:
  - threading(GIL=1)이 왜 CPU-bound에서 안 빨라지는지
  - multiprocessing은 왜 빨라지는지 (프로세스 격리 → GIL 우회)
  - Pillow(C 확장) vs 순수 Python의 GIL 영향 차이

사용법 (컨테이너 내부):
    cd /app/src && uv run python -m scripts.bench_concurrency

GIL=1로 실행해서 비교:
    cd /app/src && PYTHON_GIL=1 uv run python -m scripts.bench_concurrency
"""

import multiprocessing
import os
import sys
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

from PIL import Image

from processor import operations
from utility.timer import timer

FIXTURES_DIR = "/app/tests/fixtures"


# ============================================================
# top-level 함수 (multiprocessing pickle 호환)
# ============================================================

def _pure_python_heavy(n: int = 3_000_000) -> int:
    """순수 Python 반복 — GIL을 잡고 놓지 않는 CPU-bound 작업."""
    total = 0
    for i in range(n):
        total += i * i
    return total


def _pure_python_one(_: object) -> bool:
    """ProcessPoolExecutor용 wrapper."""
    _pure_python_heavy()
    return True


def _pillow_blur_one(path: str) -> bool:
    """Pillow blur 처리 — ProcessPoolExecutor용 top-level 함수."""
    img = Image.open(path).convert("RGB")
    operations.blur(img, radius=10)
    return True


# ============================================================
# 벤치마크 실행
# ============================================================

def _run_bench(label, count, sync_fn, thread_fn, mp_fn, workers):
    """sync / threading / multiprocessing 3가지를 실행하고 결과를 출력한다."""
    print(f"\n[ {label} ]")
    print("-" * 60)

    with timer("sync") as t:
        for _ in range(count):
            sync_fn()
    sync_time = t.elapsed
    print(f"  {'sync':<35s}  {sync_time:.3f}s  (1.00x)")

    with timer(f"threading ({workers} workers)") as t:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(lambda _: thread_fn(), range(count)))
    thread_time = t.elapsed
    ratio_t = thread_time / sync_time
    print(f"  {f'threading ({workers} workers)':<35s}  {thread_time:.3f}s  ({ratio_t:.2f}x)")

    with timer(f"multiprocessing ({workers} workers)") as t:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            list(pool.map(mp_fn, range(count)))
    mp_time = t.elapsed
    ratio_m = mp_time / sync_time
    print(f"  {f'multiprocessing ({workers} workers)':<35s}  {mp_time:.3f}s  ({ratio_m:.2f}x)")

    return sync_time, thread_time, mp_time


def _run_pillow_bench(label, images, workers):
    """Pillow 전용 벤치마크 (multiprocessing에 path 전달 필요)."""
    count = len(images)

    def blur_one(path):
        img = Image.open(path).convert("RGB")
        operations.blur(img, radius=10)

    print(f"\n[ {label} ]")
    print("-" * 60)

    with timer("sync") as t:
        for path in images:
            blur_one(path)
    sync_time = t.elapsed
    print(f"  {'sync':<35s}  {sync_time:.3f}s  (1.00x)")

    with timer(f"threading ({workers} workers)") as t:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(blur_one, images))
    thread_time = t.elapsed
    ratio_t = thread_time / sync_time
    print(f"  {f'threading ({workers} workers)':<35s}  {thread_time:.3f}s  ({ratio_t:.2f}x)")

    with timer(f"multiprocessing ({workers} workers)") as t:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            list(pool.map(_pillow_blur_one, images))
    mp_time = t.elapsed
    ratio_m = mp_time / sync_time
    print(f"  {f'multiprocessing ({workers} workers)':<35s}  {mp_time:.3f}s  ({ratio_m:.2f}x)")

    return sync_time, thread_time, mp_time


def main():
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
    workers = 4

    gil_status = "enabled" if sys._is_gil_enabled() else "disabled"

    print(f"Tasks: {count}개 | Workers: {workers} | GIL: {gil_status}")
    print("=" * 60)

    # --- 1. 순수 Python CPU-bound (GIL 영향을 명확히 보여줌) ---
    sync_p, thread_p, mp_p = _run_bench(
        f"순수 Python CPU-bound (x{count})",
        count=count,
        sync_fn=_pure_python_heavy,
        thread_fn=_pure_python_heavy,
        mp_fn=_pure_python_one,
        workers=workers,
    )

    # --- 2. Pillow 이미지 처리 (C 확장이 GIL 릴리즈) ---
    sync_i, thread_i, mp_i = _run_pillow_bench(
        f"Pillow blur x{count} (C 확장)",
        images=images,
        workers=workers,
    )

    # --- 분석 출력 ---
    print()
    print("=" * 60)
    print("분석")
    print("=" * 60)

    print()
    print("▶ 순수 Python CPU-bound:")
    if sys._is_gil_enabled():
        print(f"  threading  {thread_p / sync_p:.2f}x → GIL이 막아서 순차와 동일 (혹은 더 느림)")
        print(f"  multiproc  {mp_p / sync_p:.2f}x → 프로세스 격리로 GIL 우회, 병렬 성공")
    else:
        print(f"  threading  {thread_p / sync_p:.2f}x → GIL=0이라 스레드도 병렬 실행!")
        print(f"  multiproc  {mp_p / sync_p:.2f}x → 병렬 + 프로세스 생성 오버헤드")

    print()
    print("▶ Pillow (C 확장):")
    print(f"  threading  {thread_i / sync_i:.2f}x → C 확장이 GIL을 릴리즈하므로 GIL 상태와 무관하게 병렬")
    print(f"  multiproc  {mp_i / sync_i:.2f}x → 프로세스 격리로 항상 병렬")

    print()
    print("핵심 교훈:")
    print("  1. 순수 Python CPU-bound → GIL=1에서 threading 무의미, GIL=0이면 해결")
    print("  2. C 확장 (Pillow, NumPy 등) → 내부에서 GIL 릴리즈하므로 GIL 영향 적음")
    print("  3. multiprocessing → GIL과 무관하게 항상 병렬, 단 메모리/오버헤드 비용")


if __name__ == "__main__":
    multiprocessing.set_start_method("fork", force=True)
    main()

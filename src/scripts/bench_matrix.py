"""
4가지 동시성 방식 × 워커 수(1,2,4,8) 벤치마크 매트릭스.

Day 5 핵심 실험: free-threaded Python의 진짜 가치를 정량적으로 확인.

사용법 (컨테이너 내부):
    cd /app/src && uv run python -m scripts.bench_matrix
"""

import sys
import time

from processor import frethread_runner, mp_runner, sync_runner, thread_runner

FIXTURES_DIR = "/app/tests/fixtures"
IMAGE_COUNT = 10
WORKER_COUNTS = [1, 2, 4, 8]
OPERATION = "blur"
PARAMS = {"radius": 10}


def _get_image_paths(count: int) -> list[str]:
    import os
    paths = sorted(
        os.path.join(FIXTURES_DIR, f)
        for f in os.listdir(FIXTURES_DIR)
        if f.endswith((".jpg", ".jpeg", ".png"))
    )
    return (paths * ((count // len(paths)) + 1))[:count]


def _bench(label: str, fn) -> float:
    start = time.perf_counter()
    fn()
    elapsed = time.perf_counter() - start
    return elapsed


def main():
    images = _get_image_paths(IMAGE_COUNT)
    gil_status = "disabled" if not sys._is_gil_enabled() else "enabled"

    print(f"벤치마크 매트릭스: {IMAGE_COUNT}장 {OPERATION} | GIL: {gil_status}")
    print(f"Python {sys.version}")
    print("=" * 75)

    # sync 기준선 (workers 무관)
    sync_time = _bench("sync", lambda: sync_runner.run(images, OPERATION, PARAMS))
    print(f"\n{'방식':<25s}  {'workers':>7s}  {'시간':>8s}  {'배율':>8s}")
    print("-" * 55)
    print(f"{'sync':<25s}  {'1':>7s}  {sync_time:>7.3f}s  {'1.00x':>8s}")

    # 결과 저장 (나중에 비교용)
    results = [("sync", 1, sync_time)]

    runners = [
        ("threading (GIL)", thread_runner),
        ("multiprocessing", mp_runner),
    ]
    # frethread는 GIL=0에서만 실행 가능
    if not sys._is_gil_enabled():
        runners.append(("frethread (GIL=0)", frethread_runner))
    else:
        print("\n  (frethread 생략 — GIL=1 환경)")

    for label, runner in runners:
        for w in WORKER_COUNTS:
            t = _bench(f"{label} w={w}", lambda r=runner, w=w: r.run(images, OPERATION, PARAMS, workers=w))
            ratio = t / sync_time
            print(f"{label:<25s}  {w:>7d}  {t:>7.3f}s  {ratio:>7.2f}x")
            results.append((label, w, t))

    # 분석 출력
    print()
    print("=" * 75)
    print("분석")
    print("=" * 75)

    # 가장 빠른 결과 찾기
    fastest = min(results, key=lambda x: x[2])
    print(f"\n가장 빠른 방식: {fastest[0]} (workers={fastest[1]}) — {fastest[2]:.3f}s ({fastest[2]/sync_time:.2f}x)")

    # threading vs frethread 비교 (workers=4 기준)
    thread_4 = next((r for r in results if "threading" in r[0] and "free" not in r[0] and r[1] == 4), None)
    free_4 = next((r for r in results if "frethread" in r[0] and r[1] == 4), None)
    if thread_4 and free_4:
        print(f"\nthreading(GIL) w=4:   {thread_4[2]:.3f}s ({thread_4[2]/sync_time:.2f}x)")
        print(f"frethread(GIL=0) w=4: {free_4[2]:.3f}s ({free_4[2]/sync_time:.2f}x)")
        if free_4[2] < thread_4[2]:
            speedup = thread_4[2] / free_4[2]
            print(f"→ GIL=0이 GIL=1 대비 {speedup:.1f}배 빠름")


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.set_start_method("fork", force=True)
    main()

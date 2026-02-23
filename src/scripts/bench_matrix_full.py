"""48조합 벤치마크 매트릭스.

Day 6 Stage 5: Day 5의 16조합(10장)을 확장하여 전체 데이터 확보.

조합: 이미지 수(10,50,100) × 워커 수(1,2,4,8) × 방식(sync,threading,mp,frethread)
  - sync는 워커 수 무관 → 이미지 수 3개만
  - 나머지 3방식 × 4워커 × 3이미지 = 36
  - 합계: 3 + 36 = 39조합 (GIL=0), sync 제외 frethread 제외 시 더 적음

사용법 (컨테이너 내부):
    cd /app/src && uv run python -m scripts.bench_matrix_full
"""

import sys
import time

from processor import sync_runner, thread_runner, mp_runner, frethread_runner

FIXTURES_DIR = "/app/tests/fixtures"
IMAGE_COUNTS = [10, 50, 100]
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


def _bench(fn) -> float:
    start = time.perf_counter()
    fn()
    return time.perf_counter() - start


def main():
    gil_status = "disabled" if not sys._is_gil_enabled() else "enabled"
    print(f"48조합 벤치마크 매트릭스 | GIL: {gil_status}")
    print(f"Python {sys.version}")
    print(f"이미지 수: {IMAGE_COUNTS}, 워커: {WORKER_COUNTS}, 작업: {OPERATION}")
    print("=" * 85)

    # 방식 목록 (GIL 상태에 따라)
    runners = [
        ("threading", thread_runner),
        ("multiprocessing", mp_runner),
    ]
    if not sys._is_gil_enabled():
        runners.append(("frethread", frethread_runner))
    else:
        print("(frethread 생략 — GIL=1 환경)\n")

    # 전체 결과 저장
    all_results = []

    for img_count in IMAGE_COUNTS:
        images = _get_image_paths(img_count)

        # sync 기준선
        sync_time = _bench(lambda: sync_runner.run(images, OPERATION, PARAMS))
        all_results.append(("sync", 1, img_count, sync_time))

        print(f"\n[{img_count}장]")
        print(f"{'방식':<20s}  {'workers':>7s}  {'시간':>8s}  {'sync대비':>8s}  {'img/s':>8s}")
        print("-" * 60)
        print(f"{'sync':<20s}  {'1':>7s}  {sync_time:>7.3f}s  {'1.00x':>8s}  {img_count/sync_time:>7.1f}")

        for label, runner in runners:
            for w in WORKER_COUNTS:
                t = _bench(lambda r=runner, w=w: r.run(images, OPERATION, PARAMS, workers=w))
                ratio = t / sync_time
                ips = img_count / t if t > 0 else 0
                all_results.append((label, w, img_count, t))
                print(f"{label:<20s}  {w:>7d}  {t:>7.3f}s  {ratio:>7.2f}x  {ips:>7.1f}")

    # ── 종합 분석 ──
    print()
    print("=" * 85)
    print("종합 분석")
    print("=" * 85)

    # 이미지 수별 가장 빠른 방식
    for img_count in IMAGE_COUNTS:
        subset = [r for r in all_results if r[2] == img_count]
        fastest = min(subset, key=lambda x: x[3])
        sync_t = next(r[3] for r in subset if r[0] == "sync")
        print(f"\n{img_count}장 최적: {fastest[0]} w={fastest[1]} — {fastest[3]:.3f}s (sync대비 {fastest[3]/sync_t:.2f}x)")

    # 스케일링 분석: 100장 기준, 워커 수에 따른 변화
    print(f"\n── 100장 스케일링 (워커 증가에 따른 속도 변화) ──")
    sync_100 = next(r[3] for r in all_results if r[0] == "sync" and r[2] == 100)
    print(f"{'방식':<20s}  {'w=1':>8s}  {'w=2':>8s}  {'w=4':>8s}  {'w=8':>8s}")
    print("-" * 55)

    for method_name in ["threading", "multiprocessing", "frethread"]:
        times = []
        for w in WORKER_COUNTS:
            r = next((r for r in all_results if r[0] == method_name and r[1] == w and r[2] == 100), None)
            if r:
                times.append(f"{r[3]:.3f}s")
            else:
                times.append("  N/A  ")
        if any("N/A" not in t for t in times):
            print(f"{method_name:<20s}  {'  '.join(times)}")

    # GIL 효과 분석
    if not sys._is_gil_enabled():
        print(f"\n── GIL=0 효과 (threading vs frethread, 100장 w=4) ──")
        t_thread = next((r[3] for r in all_results if r[0] == "threading" and r[1] == 4 and r[2] == 100), None)
        t_free = next((r[3] for r in all_results if r[0] == "frethread" and r[1] == 4 and r[2] == 100), None)
        if t_thread and t_free:
            print(f"threading(GIL):    {t_thread:.3f}s")
            print(f"frethread(GIL=0):  {t_free:.3f}s")
            if t_free < t_thread:
                print(f"→ GIL=0이 {t_thread/t_free:.1f}배 빠름")


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.set_start_method("fork", force=True)
    main()

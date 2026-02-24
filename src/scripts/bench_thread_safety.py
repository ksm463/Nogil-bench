#!/usr/bin/env python3
"""Thread-safety 실험: GIL이 숨겨주던 동시성 버그를 직접 경험.

free-threaded Python(GIL=0)에서 공유 자원에 대한 race condition을 재현하고,
threading.Lock으로 해결하는 과정을 보여준다.

실험 구성:
  1. 공유 카운터 증가 (Lock 없음) — race condition으로 값 손실
  2. 공유 카운터 증가 (Lock 사용) — 정확한 결과
  3. Check-then-act 패턴 — TOCTOU race condition
  4. Check-then-act + Lock — 정확한 결과

실행:
    docker exec nogil-bench-compose uv run python src/scripts/bench_thread_safety.py
"""

import sys
import threading
import time


def _gil_status() -> str:
    return "disabled (free-threaded)" if not sys._is_gil_enabled() else "enabled"


# ── 실험 1: 공유 카운터 (Lock 없음) ─────────────────────────────────


def counter_no_lock(threads: int, increments: int) -> tuple[int, float]:
    """Lock 없이 공유 카운터를 증가시킨다.

    GIL=0에서는 read-modify-write가 원자적이지 않아
    값 손실(lost update)이 발생한다.
    """
    counter = {"value": 0}

    def _worker():
        for _ in range(increments):
            # read → modify → write: 3단계가 원자적이지 않음
            current = counter["value"]
            counter["value"] = current + 1

    workers = []
    start = time.perf_counter()
    for _ in range(threads):
        t = threading.Thread(target=_worker)
        workers.append(t)
        t.start()
    for t in workers:
        t.join()
    elapsed = time.perf_counter() - start

    return counter["value"], elapsed


# ── 실험 2: 공유 카운터 (Lock 사용) ─────────────────────────────────


def counter_with_lock(threads: int, increments: int) -> tuple[int, float]:
    """Lock으로 보호된 공유 카운터. 항상 정확한 결과."""
    counter = {"value": 0}
    lock = threading.Lock()

    def _worker():
        for _ in range(increments):
            with lock:
                current = counter["value"]
                counter["value"] = current + 1

    workers = []
    start = time.perf_counter()
    for _ in range(threads):
        t = threading.Thread(target=_worker)
        workers.append(t)
        t.start()
    for t in workers:
        t.join()
    elapsed = time.perf_counter() - start

    return counter["value"], elapsed


# ── 실험 3: Check-then-act (Lock 없음) ─────────────────────────────


def check_then_act_no_lock(threads: int, limit: int) -> tuple[list, float]:
    """Check-then-act 패턴: 리스트 크기를 확인 후 추가.

    GIL=0에서는 check와 act 사이에 다른 스레드가 끼어들어
    limit을 초과하는 항목이 추가될 수 있다 (TOCTOU 경합).
    """
    shared_list: list[int] = []

    def _worker(worker_id: int):
        for i in range(limit * 2):
            # CHECK: 리스트가 limit 미만인지 확인
            if len(shared_list) < limit:
                # ACT: 추가 (check와 act 사이에 다른 스레드가 끼어들 수 있음)
                shared_list.append(worker_id * 1000 + i)

    workers = []
    start = time.perf_counter()
    for wid in range(threads):
        t = threading.Thread(target=_worker, args=(wid,))
        workers.append(t)
        t.start()
    for t in workers:
        t.join()
    elapsed = time.perf_counter() - start

    return shared_list, elapsed


# ── 실험 4: Check-then-act (Lock 사용) ─────────────────────────────


def check_then_act_with_lock(threads: int, limit: int) -> tuple[list, float]:
    """Lock으로 check-then-act를 원자적으로 만든다."""
    shared_list: list[int] = []
    lock = threading.Lock()

    def _worker(worker_id: int):
        for i in range(limit * 2):
            with lock:
                if len(shared_list) < limit:
                    shared_list.append(worker_id * 1000 + i)

    workers = []
    start = time.perf_counter()
    for wid in range(threads):
        t = threading.Thread(target=_worker, args=(wid,))
        workers.append(t)
        t.start()
    for t in workers:
        t.join()
    elapsed = time.perf_counter() - start

    return shared_list, elapsed


# ── 메인 ────────────────────────────────────────────────────────────


def main():
    print("=" * 65)
    print("  Thread-Safety 실험: GIL이 숨겨주던 동시성 버그")
    print("=" * 65)
    print(f"  Python: {sys.version}")
    print(f"  GIL:    {_gil_status()}")
    print()

    threads = 8
    increments = 100_000
    expected = threads * increments

    # ── 실험 1 & 2: 공유 카운터 ──
    print("─" * 65)
    print(f"  실험 1-2: 공유 카운터 ({threads}스레드 × {increments:,}회 증가)")
    print(f"  기댓값: {expected:,}")
    print("─" * 65)

    # 여러 번 반복하여 race condition 발생 확률 높임
    trials = 5
    no_lock_results = []
    for trial in range(trials):
        result, elapsed = counter_no_lock(threads, increments)
        no_lock_results.append(result)
        loss = expected - result
        loss_pct = loss / expected * 100
        status = "OK" if result == expected else f"LOST {loss:,} ({loss_pct:.1f}%)"
        print(f"  [Lock 없음] trial {trial + 1}: {result:>10,} — {status}  ({elapsed:.3f}s)")

    print()

    lock_results = []
    for trial in range(trials):
        result, elapsed = counter_with_lock(threads, increments)
        lock_results.append(result)
        status = "OK" if result == expected else "ERROR"
        print(f"  [Lock 사용] trial {trial + 1}: {result:>10,} — {status}  ({elapsed:.3f}s)")

    print()
    no_lock_losses = [expected - r for r in no_lock_results]
    total_loss = sum(no_lock_losses)
    if total_loss > 0:
        loss_count = sum(1 for loss in no_lock_losses if loss > 0)
        print(f"  → Lock 없음: {trials}회 중 {loss_count}회에서 값 손실 발생")
        print(f"    평균 손실: {total_loss // trials:,} / {expected:,}")
    else:
        print("  → Lock 없음: 값 손실 없음 (GIL이 보호 중이거나 운이 좋은 경우)")

    all_correct = all(r == expected for r in lock_results)
    print(f"  → Lock 사용: {trials}회 모두 {'정확' if all_correct else '오류 발생!'}")
    print()

    # ── 실험 3 & 4: Check-then-act ──
    limit = 100_000
    print("─" * 65)
    print(f"  실험 3-4: Check-then-act ({threads}스레드, limit={limit:,})")
    print("─" * 65)

    no_lock_list, elapsed1 = check_then_act_no_lock(threads, limit)
    over = len(no_lock_list) - limit
    status1 = "OK" if len(no_lock_list) == limit else f"OVER by {over}"
    print(f"  [Lock 없음] 리스트 크기: {len(no_lock_list):,}  (limit={limit}) — {status1}  ({elapsed1:.3f}s)")

    lock_list, elapsed2 = check_then_act_with_lock(threads, limit)
    over2 = len(lock_list) - limit
    status2 = "OK" if len(lock_list) == limit else f"OVER by {over2}"
    print(f"  [Lock 사용] 리스트 크기: {len(lock_list):,}  (limit={limit}) — {status2}  ({elapsed2:.3f}s)")

    print()

    # ── 요약 ──
    print("=" * 65)
    print("  요약")
    print("=" * 65)

    if sys._is_gil_enabled():
        print("""
  GIL=1 (기존 Python):
    - GIL이 bytecode 실행을 직렬화하여 race condition이 잘 드러나지 않음
    - 그러나 이것은 '우연히 안전한 것'이지 '올바른 코드'가 아님
    - GIL=0으로 전환하면 즉시 버그가 드러남

  교훈: GIL에 의존하지 말고 항상 Lock을 사용하라
""")
    else:
        print("""
  GIL=0 (free-threaded):
    - 진짜 병렬 실행이 되므로 race condition이 즉시 드러남
    - 공유 카운터: read-modify-write 사이에 다른 스레드가 끼어들어 값 손실
    - Check-then-act: check와 act 사이에 조건이 변경되어 limit 초과

  해결: threading.Lock으로 critical section을 보호하면 정확한 결과

  실무 가이드:
    - 공유 상태를 변경하는 코드 → Lock 또는 queue.Queue 사용
    - 불변 데이터 공유 → Lock 불필요 (읽기 전용은 안전)
    - 가능하면 스레드 간 데이터 공유를 최소화하라 (thread-local, 메시지 패싱)
""")


if __name__ == "__main__":
    main()

"""Thread-safety 테스트 — GIL=0에서 race condition 재현 및 Lock 검증.

Day 7:
  free-threaded Python에서 공유 자원 접근 시 race condition을 재현하고,
  threading.Lock으로 올바르게 해결되는지 검증한다.
"""

import sys
import threading
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)

# ── 공유 카운터 테스트 ──────────────────────────────────────────────


class TestSharedCounterRaceCondition:
    """Lock 없는 공유 카운터에서 race condition을 검증."""

    def test_counter_no_lock_may_lose_updates(self):
        """Lock 없이 공유 카운터를 증가시키면 GIL=0에서 값 손실이 발생한다.

        여러 trial을 수행하여 최소 1회 이상 race condition이 발생하는지 확인.
        GIL=1에서는 손실이 안 나올 수 있으므로 조건부 assert.
        """
        threads = 8
        increments = 50_000
        expected = threads * increments
        has_loss = False

        for _ in range(10):
            counter = {"value": 0}

            def _worker():
                for _ in range(increments):
                    current = counter["value"]
                    counter["value"] = current + 1

            workers = []
            for _ in range(threads):
                t = threading.Thread(target=_worker)
                workers.append(t)
                t.start()
            for t in workers:
                t.join()

            if counter["value"] != expected:
                has_loss = True
                break

        if not sys._is_gil_enabled():
            # GIL=0: race condition이 반드시 발생해야 한다
            assert has_loss, (
                f"GIL=0인데 {expected:,}회 증가가 정확함 — race condition 미발생"
            )
        else:
            # GIL=1: GIL이 보호하므로 손실이 없을 수 있음 (테스트 통과)
            pass

    def test_counter_with_lock_always_correct(self):
        """Lock으로 보호하면 GIL 여부와 무관하게 항상 정확하다."""
        threads = 8
        increments = 50_000
        expected = threads * increments
        counter = {"value": 0}
        lock = threading.Lock()

        def _worker():
            for _ in range(increments):
                with lock:
                    current = counter["value"]
                    counter["value"] = current + 1

        workers = []
        for _ in range(threads):
            t = threading.Thread(target=_worker)
            workers.append(t)
            t.start()
        for t in workers:
            t.join()

        assert counter["value"] == expected, (
            f"Lock 사용인데 {counter['value']:,} != {expected:,}"
        )


# ── Check-then-act 패턴 테스트 ──────────────────────────────────────


class TestCheckThenActRaceCondition:
    """Check-then-act 패턴(TOCTOU)에서 race condition을 검증."""

    def test_check_then_act_no_lock_may_exceed_limit(self):
        """Lock 없는 check-then-act에서 GIL=0이면 limit을 초과할 수 있다."""
        threads = 8
        limit = 100_000
        has_overflow = False

        for _ in range(10):
            shared_list: list[int] = []

            def _worker(wid: int):
                for i in range(limit * 2):
                    if len(shared_list) < limit:
                        shared_list.append(wid * 1000 + i)

            workers = []
            for wid in range(threads):
                t = threading.Thread(target=_worker, args=(wid,))
                workers.append(t)
                t.start()
            for t in workers:
                t.join()

            if len(shared_list) > limit:
                has_overflow = True
                break

        if not sys._is_gil_enabled():
            assert has_overflow, (
                f"GIL=0인데 limit={limit} 초과 미발생 — race condition 미검출"
            )
        # GIL=1: 초과가 안 날 수 있으므로 무조건 pass

    def test_check_then_act_with_lock_respects_limit(self):
        """Lock으로 check-then-act를 원자적으로 만들면 limit이 정확히 지켜진다."""
        threads = 8
        limit = 100_000
        shared_list: list[int] = []
        lock = threading.Lock()

        def _worker(wid: int):
            for i in range(limit * 2):
                with lock:
                    if len(shared_list) < limit:
                        shared_list.append(wid * 1000 + i)

        workers = []
        for wid in range(threads):
            t = threading.Thread(target=_worker, args=(wid,))
            workers.append(t)
            t.start()
        for t in workers:
            t.join()

        assert len(shared_list) == limit, (
            f"Lock 사용인데 리스트 크기 {len(shared_list)} != {limit}"
        )


# ── ThreadPoolExecutor + 공유 딕셔너리 ──────────────────────────────


class TestSharedDictRaceCondition:
    """ThreadPoolExecutor로 공유 딕셔너리에 대한 race condition 검증."""

    def test_dict_accumulator_no_lock_may_lose(self):
        """Lock 없이 공유 딕셔너리의 값을 누적하면 GIL=0에서 값 손실."""
        threads = 8
        iterations = 10_000
        expected = threads * iterations
        has_loss = False

        for _ in range(10):
            shared = {"total": 0}

            def _accumulate(_tid: int) -> int:
                for _ in range(iterations):
                    shared["total"] = shared["total"] + 1
                return _tid

            with ThreadPoolExecutor(max_workers=threads) as pool:
                futures = [pool.submit(_accumulate, tid) for tid in range(threads)]
                for f in as_completed(futures):
                    f.result()

            if shared["total"] != expected:
                has_loss = True
                break

        if not sys._is_gil_enabled():
            assert has_loss, (
                f"GIL=0인데 딕셔너리 누적 {expected:,}이 정확 — race condition 미발생"
            )

    def test_dict_accumulator_with_lock_correct(self):
        """Lock으로 보호하면 딕셔너리 누적이 정확하다."""
        threads = 8
        iterations = 10_000
        expected = threads * iterations
        shared = {"total": 0}
        lock = threading.Lock()

        def _accumulate(_tid: int) -> int:
            for _ in range(iterations):
                with lock:
                    shared["total"] = shared["total"] + 1
            return _tid

        with ThreadPoolExecutor(max_workers=threads) as pool:
            futures = [pool.submit(_accumulate, tid) for tid in range(threads)]
            for f in as_completed(futures):
                f.result()

        assert shared["total"] == expected, (
            f"Lock 사용인데 {shared['total']:,} != {expected:,}"
        )

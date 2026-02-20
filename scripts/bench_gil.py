"""
GIL=1 vs GIL=0 간단한 벤치마크 스크립트

사용법 (컨테이너 내부):
    PYTHON_GIL=0 uv run python scripts/bench_gil.py   # GIL 비활성화
    PYTHON_GIL=1 uv run python scripts/bench_gil.py   # GIL 활성화
"""

import sys
import threading
import time


def fib(n: int) -> int:
    """CPU-bound 작업: 재귀 피보나치"""
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)


def run_sequential(n: int, count: int) -> float:
    """순차 실행"""
    start = time.perf_counter()
    for _ in range(count):
        fib(n)
    return time.perf_counter() - start


def run_threaded(n: int, count: int, workers: int) -> float:
    """멀티스레드 실행"""
    threads = []
    start = time.perf_counter()
    for _ in range(workers):
        t = threading.Thread(target=fib, args=(n,))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    return time.perf_counter() - start


def main():
    n = 34
    workers = 4

    print(f"Python {sys.version}")
    print(f"GIL enabled: {sys._is_gil_enabled()}")
    print(f"Task: fib({n}) x {workers}")
    print("-" * 40)

    # 순차 실행
    seq_time = run_sequential(n, workers)
    print(f"Sequential ({workers}회):   {seq_time:.2f}s")

    # 멀티스레드 실행
    thr_time = run_threaded(n, workers, workers)
    print(f"Threaded   ({workers} threads): {thr_time:.2f}s")

    # 비교
    speedup = seq_time / thr_time
    print("-" * 40)
    print(f"Speedup: {speedup:.2f}x")

    if speedup > 1.5:
        print("→ 스레드가 실제로 병렬 실행됨 (GIL 비활성화)")
    else:
        print("→ GIL이 병렬 실행을 막고 있음")


if __name__ == "__main__":
    main()

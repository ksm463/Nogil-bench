"""커넥션 풀 크기가 성능에 미치는 영향 실험.

Day 6 Stage 4: pool_size가 왜 중요한지, 어떤 값이 적절한지 체감한다.

실험 설계:
  - pool_size: 1, 5, 10, 20
  - max_overflow: 0 (풀 초과 차단 → 풀 크기 효과를 정확히 측정)
  - 20개 동시 스레드가 각 5회 DB 쓰기
  - 측정: 총 시간, timeout 에러 수

핵심 질문: "pool_size=1이면 20개 스레드가 어떻게 되는가?"
  → 커넥션 1개를 20명이 돌려쓰며 기다려야 함 → 심한 병목

사용법 (compose 컨테이너 내부):
    cd /app/src && uv run python -m scripts.bench_db_pool
"""

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

POOL_SIZES = [1, 5, 10, 20]
THREADS = 20
WRITES_PER_THREAD = 5
# 커넥션을 기다리는 최대 시간 (초)
POOL_TIMEOUT = 3


def _get_pg_dsn() -> str:
    """환경변수에서 PostgreSQL DSN을 가져온다."""
    dsn = os.environ.get("DATABASE_URL", "")
    if dsn.startswith("postgresql+psycopg://"):
        dsn = dsn.replace("postgresql+psycopg://", "postgresql://")
    return dsn


def _setup_table(dsn: str) -> None:
    """테스트 테이블 초기화."""
    import psycopg
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS pool_bench")
        conn.execute("""
            CREATE TABLE pool_bench (
                id SERIAL PRIMARY KEY,
                thread_id INTEGER,
                seq INTEGER,
                created_at DOUBLE PRECISION
            )
        """)


def _worker(pool, thread_id: int, writes: int) -> dict:
    """풀에서 커넥션을 가져와 쓰기를 수행한다."""
    success = 0
    timeout_err = 0

    for seq in range(writes):
        try:
            conn = pool.getconn()
            try:
                conn.execute(
                    "INSERT INTO pool_bench (thread_id, seq, created_at) VALUES (%s, %s, %s)",
                    (thread_id, seq, time.time()),
                )
                conn.commit()
                success += 1
            finally:
                pool.putconn(conn)
        except Exception as e:
            if "timeout" in str(e).lower() or "pool" in str(e).lower():
                timeout_err += 1
            else:
                timeout_err += 1
    return {"success": success, "timeout": timeout_err}


def _run_pool_test(dsn: str, pool_size: int) -> dict:
    """특정 pool_size로 동시 쓰기 테스트."""
    from psycopg_pool import ConnectionPool

    _setup_table(dsn)

    pool = ConnectionPool(
        dsn,
        min_size=pool_size,
        max_size=pool_size,  # max_overflow=0 효과: 풀 크기 고정
        timeout=POOL_TIMEOUT,
    )
    pool.wait()  # 풀 초기화 대기

    start = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        futures = {
            executor.submit(_worker, pool, tid, WRITES_PER_THREAD): tid
            for tid in range(THREADS)
        }
        for f in as_completed(futures):
            results.append(f.result())
    elapsed = time.perf_counter() - start

    pool.close()

    total_success = sum(r["success"] for r in results)
    total_timeout = sum(r["timeout"] for r in results)
    expected = THREADS * WRITES_PER_THREAD
    wps = total_success / elapsed if elapsed > 0 else 0

    return {
        "pool_size": pool_size,
        "threads": THREADS,
        "expected": expected,
        "success": total_success,
        "timeout": total_timeout,
        "elapsed": elapsed,
        "wps": wps,
    }


def main():
    dsn = _get_pg_dsn()
    if not dsn or "sqlite" in dsn:
        print("⚠ PostgreSQL DSN이 필요합니다. docker-compose 환경에서 실행하세요.")
        return

    gil_status = "disabled" if not sys._is_gil_enabled() else "enabled"
    print(f"커넥션 풀 크기 실험 | GIL: {gil_status}")
    print(f"Python {sys.version}")
    print(f"{THREADS}개 스레드, 스레드당 {WRITES_PER_THREAD}회 쓰기, pool timeout={POOL_TIMEOUT}s")
    print("=" * 70)

    print(f"\n{'pool_size':>10s}  {'예상':>5s}  {'성공':>5s}  {'timeout':>7s}  {'시간':>8s}  {'writes/s':>10s}")
    print("-" * 55)

    results = []
    for ps in POOL_SIZES:
        r = _run_pool_test(dsn, ps)
        results.append(r)
        print(
            f"{r['pool_size']:>10d}  {r['expected']:>5d}  {r['success']:>5d}  "
            f"{r['timeout']:>7d}  {r['elapsed']:>7.3f}s  {r['wps']:>9.0f}"
        )

    # ── 분석 ──
    print()
    print("=" * 70)
    print("분석")
    print("=" * 70)

    fastest = min(results, key=lambda x: x["elapsed"])
    slowest = max(results, key=lambda x: x["elapsed"])
    print(f"\n가장 빠른: pool_size={fastest['pool_size']} — {fastest['elapsed']:.3f}s ({fastest['wps']:.0f} w/s)")
    print(f"가장 느린: pool_size={slowest['pool_size']} — {slowest['elapsed']:.3f}s ({slowest['wps']:.0f} w/s)")

    if slowest["wps"] > 0:
        print(f"차이: {fastest['wps']/slowest['wps']:.1f}배")

    print()
    print("핵심 관찰:")
    print("  - pool_size=1: 커넥션 1개를 20개 스레드가 돌려씀 → 심한 병목")
    print("  - pool_size≈동시 사용자 수: 대기 없이 바로 처리 → 최적")
    print("  - pool_size를 과하게 늘려도 DB 서버 자원 낭비만 증가")
    print()
    print("실무 가이드:")
    print("  pool_size = 예상 동시 요청 수 (보통 5~20)")
    print("  max_overflow = 갑작스런 트래픽 대비 여유분 (보통 pool_size와 동일)")


if __name__ == "__main__":
    main()

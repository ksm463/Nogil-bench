"""SQLite vs PostgreSQL 동시 쓰기 벤치마크.

Day 6 Stage 3: 동일한 워크로드로 두 DB를 비교하여 MVCC의 가치를 정량적으로 확인한다.

실험 설계:
  - 스레드 수: 1, 2, 4, 8, 16
  - 스레드당 100건 INSERT
  - 측정: 성공/실패 수, writes/sec, 총 시간
  - 기대: SQLite는 스레드 늘려도 처리량 정체, PostgreSQL은 증가

사용법 (compose 컨테이너 내부):
    cd /app/src && uv run python -m scripts.bench_db_write
    cd /app/src && uv run python -m scripts.bench_db_write --db sqlite
    cd /app/src && uv run python -m scripts.bench_db_write --db postgresql
"""

import argparse
import os
import sqlite3
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROWS_PER_THREAD = 100
THREAD_COUNTS = [1, 2, 4, 8, 16]


# ── SQLite 워커 ──

def _sqlite_create(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bench (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id INTEGER,
            value TEXT,
            created_at REAL
        )
    """)
    conn.commit()
    conn.close()


def _sqlite_writer(db_path: str, thread_id: int, rows: int) -> dict:
    success = 0
    locked = 0
    conn = sqlite3.connect(db_path, timeout=5.0)
    for i in range(rows):
        try:
            conn.execute(
                "INSERT INTO bench (thread_id, value, created_at) VALUES (?, ?, ?)",
                (thread_id, f"data-{thread_id}-{i}", time.time()),
            )
            conn.commit()
            success += 1
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                locked += 1
            else:
                raise
    conn.close()
    return {"success": success, "failed": locked}


# ── PostgreSQL 워커 ──

def _pg_create(dsn: str) -> None:
    import psycopg
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS bench")
        conn.execute("""
            CREATE TABLE bench (
                id SERIAL PRIMARY KEY,
                thread_id INTEGER,
                value TEXT,
                created_at DOUBLE PRECISION
            )
        """)


def _pg_writer(dsn: str, thread_id: int, rows: int) -> dict:
    import psycopg
    success = 0
    failed = 0
    conn = psycopg.connect(dsn, autocommit=True)
    for i in range(rows):
        try:
            conn.execute(
                "INSERT INTO bench (thread_id, value, created_at) VALUES (%s, %s, %s)",
                (thread_id, f"data-{thread_id}-{i}", time.time()),
            )
            success += 1
        except Exception:
            failed += 1
    conn.close()
    return {"success": success, "failed": failed}


# ── 벤치마크 실행 ──

def _run(label: str, worker_fn, worker_args_fn, threads: int) -> dict:
    """N개 스레드로 동시 쓰기를 실행하고 결과를 반환."""
    start = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=threads) as pool:
        futures = {
            pool.submit(worker_fn, *worker_args_fn(tid), tid, ROWS_PER_THREAD): tid
            for tid in range(threads)
        }
        for f in as_completed(futures):
            results.append(f.result())
    elapsed = time.perf_counter() - start

    total_success = sum(r["success"] for r in results)
    total_failed = sum(r["failed"] for r in results)
    expected = threads * ROWS_PER_THREAD
    wps = total_success / elapsed if elapsed > 0 else 0

    return {
        "label": label,
        "threads": threads,
        "expected": expected,
        "success": total_success,
        "failed": total_failed,
        "elapsed": elapsed,
        "wps": wps,
    }


def _print_header():
    print(f"{'DB':<14s}  {'스레드':>4s}  {'예상':>5s}  {'성공':>5s}  {'실패':>4s}  {'시간':>8s}  {'writes/s':>10s}")
    print("-" * 62)


def _print_row(r: dict):
    print(
        f"{r['label']:<14s}  {r['threads']:>4d}  {r['expected']:>5d}  "
        f"{r['success']:>5d}  {r['failed']:>4d}  {r['elapsed']:>7.3f}s  "
        f"{r['wps']:>9.0f}"
    )


def bench_sqlite() -> list[dict]:
    """SQLite (WAL 모드, timeout=5s) 벤치마크."""
    tmpdir = tempfile.mkdtemp(prefix="bench_write_")
    results = []
    for t in THREAD_COUNTS:
        db_path = os.path.join(tmpdir, f"sqlite_{t}.db")
        _sqlite_create(db_path)
        r = _run(
            "SQLite",
            _sqlite_writer,
            lambda tid, p=db_path: (p,),
            t,
        )
        results.append(r)
        _print_row(r)
    return results


def bench_pg(dsn: str) -> list[dict]:
    """PostgreSQL 벤치마크."""
    results = []
    for t in THREAD_COUNTS:
        _pg_create(dsn)
        r = _run(
            "PostgreSQL",
            _pg_writer,
            lambda tid, d=dsn: (d,),
            t,
        )
        results.append(r)
        _print_row(r)
    return results


def main():
    parser = argparse.ArgumentParser(description="SQLite vs PostgreSQL 동시 쓰기 벤치마크")
    parser.add_argument("--db", choices=["sqlite", "postgresql", "both"], default="both")
    args = parser.parse_args()

    # PostgreSQL DSN 결정
    pg_dsn = os.environ.get("DATABASE_URL", "")
    # SQLAlchemy URL → psycopg URL 변환
    if pg_dsn.startswith("postgresql+psycopg://"):
        pg_dsn = pg_dsn.replace("postgresql+psycopg://", "postgresql://")

    gil_status = "disabled" if not sys._is_gil_enabled() else "enabled"
    print(f"SQLite vs PostgreSQL 동시 쓰기 벤치마크 | GIL: {gil_status}")
    print(f"Python {sys.version}")
    print(f"스레드당 {ROWS_PER_THREAD}건 INSERT, timeout=5s(SQLite)")
    print("=" * 62)

    sqlite_results = []
    pg_results = []

    if args.db in ("sqlite", "both"):
        print("\n[SQLite — WAL 모드]")
        _print_header()
        sqlite_results = bench_sqlite()

    if args.db in ("postgresql", "both"):
        if not pg_dsn or "sqlite" in pg_dsn:
            print("\n⚠ PostgreSQL DSN이 설정되지 않음 (DATABASE_URL 환경변수 확인)")
            print("  docker-compose 환경에서 실행하세요.")
        else:
            print(f"\n[PostgreSQL]")
            _print_header()
            pg_results = bench_pg(pg_dsn)

    # ── 비교 분석 ──
    if sqlite_results and pg_results:
        print()
        print("=" * 62)
        print("비교 분석")
        print("=" * 62)

        print(f"\n{'스레드':>4s}  {'SQLite w/s':>12s}  {'PG w/s':>12s}  {'PG/SQLite':>10s}")
        print("-" * 44)
        for s, p in zip(sqlite_results, pg_results):
            ratio = p["wps"] / s["wps"] if s["wps"] > 0 else float("inf")
            print(f"{s['threads']:>4d}  {s['wps']:>11.0f}  {p['wps']:>11.0f}  {ratio:>9.1f}x")

        # 16스레드 기준 비교
        s16 = sqlite_results[-1]
        p16 = pg_results[-1]
        print(f"\n16스레드 기준:")
        print(f"  SQLite:     {s16['wps']:.0f} writes/s (실패 {s16['failed']}건)")
        print(f"  PostgreSQL: {p16['wps']:.0f} writes/s (실패 {p16['failed']}건)")
        if p16["wps"] > s16["wps"]:
            print(f"  → PostgreSQL이 {p16['wps']/s16['wps']:.1f}배 빠름")

        print()
        print("핵심 관찰:")
        print("  - SQLite: 스레드 늘려도 writes/s가 정체 (파일 잠금 → 직렬화)")
        print("  - PostgreSQL: 스레드에 비례하여 writes/s 증가 (MVCC → 병렬 쓰기)")


if __name__ == "__main__":
    main()

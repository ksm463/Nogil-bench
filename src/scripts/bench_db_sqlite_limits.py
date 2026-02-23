"""SQLite 동시성 한계 실험.

Day 6 Stage 1: SQLite의 파일 레벨 락이 동시 쓰기에 어떤 한계를 보이는지 체감한다.

실험 내용:
  1. 기본 저널 모드(DELETE)에서 8 스레드 동시 INSERT → database is locked 에러 재현
  2. WAL 모드에서 동일 실험 → 읽기 동시성 개선 확인
  3. GIL=0 환경에서 진짜 병렬 스레드의 동시 접근 문제 심화 확인

사용법 (컨테이너 내부):
    cd /app/src && uv run python -m scripts.bench_db_sqlite_limits
"""

import os
import sqlite3
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROWS_PER_THREAD = 100
THREAD_COUNTS = [1, 2, 4, 8]


def _create_db(db_path: str, wal: bool = False) -> None:
    """테스트용 테이블 생성. WAL 모드 선택 가능."""
    conn = sqlite3.connect(db_path)
    if wal:
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


def _writer(db_path: str, thread_id: int, rows: int, timeout: float) -> dict:
    """단일 스레드의 INSERT 워크로드. 성공/실패 수를 반환."""
    success = 0
    locked = 0
    errors = 0
    conn = sqlite3.connect(db_path, timeout=timeout)
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
                errors += 1
    conn.close()
    return {"success": success, "locked": locked, "errors": errors}


def _run_experiment(label: str, db_path: str, threads: int, timeout: float) -> dict:
    """N개 스레드로 동시 쓰기 실험을 실행하고 결과를 반환."""
    start = time.perf_counter()
    results = []
    with ThreadPoolExecutor(max_workers=threads) as pool:
        futures = {
            pool.submit(_writer, db_path, tid, ROWS_PER_THREAD, timeout): tid
            for tid in range(threads)
        }
        for future in as_completed(futures):
            results.append(future.result())
    elapsed = time.perf_counter() - start

    total_success = sum(r["success"] for r in results)
    total_locked = sum(r["locked"] for r in results)
    total_errors = sum(r["errors"] for r in results)
    expected = threads * ROWS_PER_THREAD
    writes_per_sec = total_success / elapsed if elapsed > 0 else 0

    return {
        "label": label,
        "threads": threads,
        "expected": expected,
        "success": total_success,
        "locked": total_locked,
        "errors": total_errors,
        "elapsed": elapsed,
        "writes_per_sec": writes_per_sec,
    }


def main():
    gil_status = "disabled" if not sys._is_gil_enabled() else "enabled"
    print(f"SQLite 동시성 한계 실험 | GIL: {gil_status}")
    print(f"Python {sys.version}")
    print(f"스레드당 {ROWS_PER_THREAD}행 INSERT")
    print("=" * 80)

    tmpdir = tempfile.mkdtemp(prefix="sqlite_bench_")

    # ── 실험 1: 기본 저널 모드 (DELETE) + 매우 짧은 timeout ──
    print("\n[실험 1] 기본 저널 모드 (DELETE) — timeout=0.05s (잠금 충돌 체감)")
    print(f"{'스레드':>6s}  {'예상':>6s}  {'성공':>6s}  {'잠금':>6s}  {'에러':>6s}  {'시간':>8s}  {'writes/s':>10s}")
    print("-" * 65)

    for t in THREAD_COUNTS:
        db_path = os.path.join(tmpdir, f"delete_{t}.db")
        _create_db(db_path, wal=False)
        r = _run_experiment(f"DELETE t={t}", db_path, t, timeout=0.05)
        print(
            f"{r['threads']:>6d}  {r['expected']:>6d}  {r['success']:>6d}  "
            f"{r['locked']:>6d}  {r['errors']:>6d}  {r['elapsed']:>7.3f}s  "
            f"{r['writes_per_sec']:>9.0f}"
        )

    # ── 실험 2: WAL 모드 + 짧은 timeout ──
    print("\n[실험 2] WAL 모드 — timeout=0.05s (읽기 동시성 개선, 쓰기는?)")
    print(f"{'스레드':>6s}  {'예상':>6s}  {'성공':>6s}  {'잠금':>6s}  {'에러':>6s}  {'시간':>8s}  {'writes/s':>10s}")
    print("-" * 65)

    for t in THREAD_COUNTS:
        db_path = os.path.join(tmpdir, f"wal_{t}.db")
        _create_db(db_path, wal=True)
        r = _run_experiment(f"WAL t={t}", db_path, t, timeout=0.05)
        print(
            f"{r['threads']:>6d}  {r['expected']:>6d}  {r['success']:>6d}  "
            f"{r['locked']:>6d}  {r['errors']:>6d}  {r['elapsed']:>7.3f}s  "
            f"{r['writes_per_sec']:>9.0f}"
        )

    # ── 실험 3: WAL 모드 + 넉넉한 timeout (재시도 비용 체감) ──
    print("\n[실험 3] WAL 모드 — timeout=5s (잠금 대기하면 성공하지만 느림)")
    print(f"{'스레드':>6s}  {'예상':>6s}  {'성공':>6s}  {'잠금':>6s}  {'에러':>6s}  {'시간':>8s}  {'writes/s':>10s}")
    print("-" * 65)

    for t in THREAD_COUNTS:
        db_path = os.path.join(tmpdir, f"wal_wait_{t}.db")
        _create_db(db_path, wal=True)
        r = _run_experiment(f"WAL-wait t={t}", db_path, t, timeout=5.0)
        print(
            f"{r['threads']:>6d}  {r['expected']:>6d}  {r['success']:>6d}  "
            f"{r['locked']:>6d}  {r['errors']:>6d}  {r['elapsed']:>7.3f}s  "
            f"{r['writes_per_sec']:>9.0f}"
        )

    # ── 분석 ──
    print()
    print("=" * 80)
    print("분석")
    print("=" * 80)
    print()
    print("핵심 관찰 포인트:")
    print("  1. DELETE 모드: 스레드 늘릴수록 'locked' 에러 급증 → 파일 레벨 배타 잠금")
    print("  2. WAL 모드 + 짧은 timeout: 읽기는 개선되지만 동시 쓰기는 여전히 직렬화")
    print("  3. WAL + 긴 timeout: 에러 없지만 writes/sec이 스레드 수에 비례하지 않음")
    if not sys._is_gil_enabled():
        print("  4. GIL=0에서 진짜 병렬 실행 → 잠금 경합이 GIL=1보다 더 심함")
    print()
    print("결론: SQLite는 동시 쓰기를 직렬화할 수밖에 없는 구조적 한계가 있다.")
    print("      → 이것이 PostgreSQL(MVCC)을 도입해야 하는 근본적인 이유.")


if __name__ == "__main__":
    main()

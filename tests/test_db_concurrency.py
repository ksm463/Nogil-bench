"""DB 동시성 테스트 — SQLite 한계 + PostgreSQL 동시 쓰기 검증.

Day 6:
  Stage 1 — 파일 기반 SQLite의 동시 쓰기 한계와 WAL 모드 효과
  Stage 5 — PostgreSQL의 MVCC 동시 쓰기 + 커넥션 풀 처리량 차이
"""

import os
import sqlite3
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest


@pytest.fixture()
def tmp_db(tmp_path):
    """임시 SQLite DB 파일 경로를 반환한다."""
    return str(tmp_path / "test.db")


def _create_table(db_path: str, wal: bool = False) -> None:
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


def _insert_rows(db_path: str, thread_id: int, count: int, timeout: float) -> dict:
    """N개 행을 INSERT하고 성공/실패 수를 반환."""
    success = 0
    locked = 0
    conn = sqlite3.connect(db_path, timeout=timeout)
    for i in range(count):
        try:
            conn.execute(
                "INSERT INTO bench (thread_id, value, created_at) VALUES (?, ?, ?)",
                (thread_id, f"val-{i}", time.time()),
            )
            conn.commit()
            success += 1
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                locked += 1
            else:
                raise
    conn.close()
    return {"success": success, "locked": locked}


class TestSQLiteConcurrentWrites:
    """파일 기반 SQLite에 여러 스레드가 동시 쓰기할 때 경합을 검증."""

    def test_concurrent_writes_cause_contention(self, tmp_db):
        """8 스레드가 동시에 INSERT하면 'database is locked' 에러가 발생해야 한다.

        timeout을 매우 짧게(0.01s) 설정하여 잠금 대기 없이 즉시 실패하게 한다.
        """
        _create_table(tmp_db, wal=False)
        threads = 8
        rows_per_thread = 50
        results = []

        with ThreadPoolExecutor(max_workers=threads) as pool:
            futures = [
                pool.submit(_insert_rows, tmp_db, tid, rows_per_thread, 0.01)
                for tid in range(threads)
            ]
            for f in as_completed(futures):
                results.append(f.result())

        total_locked = sum(r["locked"] for r in results)
        total_success = sum(r["success"] for r in results)

        # 8 스레드 동시 접근 시 잠금 에러가 발생해야 한다
        assert total_locked > 0, "경합이 전혀 발생하지 않음 — timeout이 너무 길거나 스레드가 직렬화됨"
        # 성공한 것도 있어야 한다
        assert total_success > 0

    def test_single_thread_no_contention(self, tmp_db):
        """단일 스레드에서는 잠금 에러가 발생하지 않는다 (대조군)."""
        _create_table(tmp_db, wal=False)
        result = _insert_rows(tmp_db, 0, 100, 0.01)
        assert result["locked"] == 0
        assert result["success"] == 100


class TestWALMode:
    """WAL 모드가 동시성에 미치는 영향을 검증."""

    def test_wal_mode_improves_read_concurrency(self, tmp_db):
        """WAL 모드에서는 쓰기 중에도 읽기가 가능하다."""
        _create_table(tmp_db, wal=True)

        # 먼저 데이터 삽입
        conn_w = sqlite3.connect(tmp_db, timeout=5)
        for i in range(100):
            conn_w.execute(
                "INSERT INTO bench (thread_id, value, created_at) VALUES (?, ?, ?)",
                (0, f"val-{i}", time.time()),
            )
        conn_w.commit()

        # 쓰기 트랜잭션 시작 (커밋하지 않음)
        conn_w.execute("BEGIN IMMEDIATE")
        conn_w.execute(
            "INSERT INTO bench (thread_id, value, created_at) VALUES (?, ?, ?)",
            (99, "writing", time.time()),
        )

        # WAL 모드에서는 쓰기 중에도 다른 커넥션이 읽기 가능
        conn_r = sqlite3.connect(tmp_db, timeout=1)
        rows = conn_r.execute("SELECT COUNT(*) FROM bench").fetchone()[0]
        assert rows == 100  # 아직 커밋 안 된 행은 안 보임

        conn_w.commit()
        conn_w.close()
        conn_r.close()

    def test_wal_concurrent_writes_still_serialized(self, tmp_db):
        """WAL 모드에서도 동시 쓰기는 직렬화된다 (잠금 발생 가능)."""
        _create_table(tmp_db, wal=True)
        threads = 8
        rows_per_thread = 50
        results = []

        with ThreadPoolExecutor(max_workers=threads) as pool:
            futures = [
                pool.submit(_insert_rows, tmp_db, tid, rows_per_thread, 0.01)
                for tid in range(threads)
            ]
            for f in as_completed(futures):
                results.append(f.result())

        total_locked = sum(r["locked"] for r in results)
        total_success = sum(r["success"] for r in results)

        # WAL에서도 동시 쓰기 시 잠금은 발생할 수 있다
        # (DELETE 모드보다는 적을 수 있지만, 여전히 직렬화됨)
        assert total_success > 0
        # 총 시도 대비 잠금 비율을 기록만 함 (WAL에서도 잠금 가능)
        total = threads * rows_per_thread
        lock_ratio = total_locked / total * 100
        print(f"WAL 모드 잠금 비율: {lock_ratio:.1f}% ({total_locked}/{total})")

    def test_long_timeout_avoids_errors(self, tmp_db):
        """timeout을 길게 설정하면 잠금 대기 후 결국 성공한다."""
        _create_table(tmp_db, wal=True)
        threads = 4
        rows_per_thread = 30
        results = []

        with ThreadPoolExecutor(max_workers=threads) as pool:
            futures = [
                pool.submit(_insert_rows, tmp_db, tid, rows_per_thread, 10.0)
                for tid in range(threads)
            ]
            for f in as_completed(futures):
                results.append(f.result())

        total_locked = sum(r["locked"] for r in results)
        total_success = sum(r["success"] for r in results)

        # 긴 timeout이면 전부 성공해야 한다
        assert total_locked == 0, f"timeout=10s인데 잠금 에러 {total_locked}건 발생"
        assert total_success == threads * rows_per_thread


# ── PostgreSQL 동시성 테스트 (integration marker, pg_engine fixture 필요) ──

def _pg_insert(engine, thread_id: int, count: int) -> dict:
    """SQLModel 엔진으로 N행 INSERT."""
    from sqlmodel import Session as SmSession, text
    success = 0
    for i in range(count):
        with SmSession(engine) as s:
            s.exec(
                text(
                    "INSERT INTO pg_bench (thread_id, value, created_at) "
                    "VALUES (:tid, :val, :ts)"
                ),
                params={"tid": thread_id, "val": f"v-{i}", "ts": time.time()},
            )
            s.commit()
            success += 1
    return {"success": success}


@pytest.mark.integration
class TestPostgreSQLConcurrency:
    """PostgreSQL MVCC 동시 쓰기 검증. TEST_DATABASE_URL 필요."""

    @pytest.fixture(autouse=True)
    def _setup_table(self, pg_engine):
        """테스트마다 pg_bench 테이블 초기화."""
        from sqlmodel import text
        with pg_engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS pg_bench"))
            conn.execute(text("""
                CREATE TABLE pg_bench (
                    id SERIAL PRIMARY KEY,
                    thread_id INTEGER,
                    value TEXT,
                    created_at DOUBLE PRECISION
                )
            """))
            conn.commit()
        self.engine = pg_engine

    def test_concurrent_writes_all_succeed(self):
        """8 스레드 동시 쓰기가 전부 성공해야 한다 (MVCC)."""
        threads = 8
        rows_per_thread = 20
        results = []

        with ThreadPoolExecutor(max_workers=threads) as pool:
            futures = [
                pool.submit(_pg_insert, self.engine, tid, rows_per_thread)
                for tid in range(threads)
            ]
            for f in as_completed(futures):
                results.append(f.result())

        total = sum(r["success"] for r in results)
        expected = threads * rows_per_thread
        assert total == expected, f"PostgreSQL에서 {expected}건 중 {total}건만 성공"

    def test_pool_size_affects_throughput(self):
        """pool_size 1 vs 10에서 처리량 차이가 있어야 한다."""
        from sqlmodel import create_engine, text
        import os

        url = os.environ["TEST_DATABASE_URL"]
        threads = 10
        rows = 10

        timings = {}
        for pool_size in [1, 10]:
            eng = create_engine(url, pool_size=pool_size, max_overflow=0)

            # 테이블 초기화
            with eng.connect() as conn:
                conn.execute(text("DELETE FROM pg_bench"))
                conn.commit()

            start = time.perf_counter()
            results = []
            with ThreadPoolExecutor(max_workers=threads) as pool:
                futures = [
                    pool.submit(_pg_insert, eng, tid, rows)
                    for tid in range(threads)
                ]
                for f in as_completed(futures):
                    results.append(f.result())
            elapsed = time.perf_counter() - start
            eng.dispose()

            total = sum(r["success"] for r in results)
            assert total == threads * rows
            timings[pool_size] = elapsed

        # pool_size=10이 pool_size=1보다 빨라야 한다
        print(f"pool_size=1: {timings[1]:.3f}s, pool_size=10: {timings[10]:.3f}s")
        assert timings[10] < timings[1], (
            f"pool_size=10({timings[10]:.3f}s)이 pool_size=1({timings[1]:.3f}s)보다 느림"
        )

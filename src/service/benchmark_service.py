"""벤치마크 실행 및 결과 관리 서비스."""

import os
import sys
import time

from sqlmodel import Session, select

from core.exceptions import BenchmarkNotFound, InvalidMethod, InvalidOperation
from model.benchmark import BenchmarkResult
from processor import frethread_runner, mp_runner, sync_runner, thread_runner

METHODS = {
    "sync": sync_runner,
    "threading": thread_runner,
    "multiprocessing": mp_runner,
    "frethread": frethread_runner,
}

OPERATIONS = {"blur", "grayscale", "resize", "rotate", "sharpen", "watermark"}

FIXTURES_DIR = "/app/tests/fixtures"


def _get_image_paths(count: int) -> list[str]:
    """테스트 이미지 경로를 count개만큼 반복하여 반환한다."""
    paths = sorted(
        os.path.join(FIXTURES_DIR, f)
        for f in os.listdir(FIXTURES_DIR)
        if f.endswith((".jpg", ".jpeg", ".png"))
    )
    return (paths * ((count // len(paths)) + 1))[:count]


def run_benchmark(
    method: str,
    operation: str,
    workers: int,
    image_count: int,
    params: dict | None,
    user_id: int,
    session: Session,
) -> BenchmarkResult:
    """벤치마크를 실행하고 결과를 DB에 저장한다."""
    if method not in METHODS:
        raise InvalidMethod(f"지원하지 않는 방식: {method}. 가능한 값: {list(METHODS.keys())}")
    if operation not in OPERATIONS:
        raise InvalidOperation(f"지원하지 않는 작업: {operation}. 가능한 값: {list(OPERATIONS)}")

    runner = METHODS[method]
    image_paths = _get_image_paths(image_count)
    params = params or {}

    # operation별 기본 params
    if operation == "resize" and not params:
        params = {"width": 200, "height": 200}
    if operation == "blur" and not params:
        params = {"radius": 10}

    start = time.perf_counter()
    if method == "sync":
        runner.run(image_paths, operation, params)
    else:
        runner.run(image_paths, operation, params, workers=workers)
    duration = time.perf_counter() - start

    result = BenchmarkResult(
        method=method,
        operation=operation,
        workers=workers if method != "sync" else 1,
        image_count=image_count,
        duration=round(duration, 4),
        gil_enabled=sys._is_gil_enabled(),
        user_id=user_id,
    )
    session.add(result)
    session.commit()
    session.refresh(result)
    return result


def list_benchmarks(user_id: int, session: Session) -> list[BenchmarkResult]:
    """해당 사용자의 벤치마크 결과 목록을 반환한다."""
    return list(
        session.exec(
            select(BenchmarkResult)
            .where(BenchmarkResult.user_id == user_id)
            .order_by(BenchmarkResult.created_at.desc())
        ).all()
    )


def get_benchmark(benchmark_id: int, user_id: int, session: Session) -> BenchmarkResult:
    """벤치마크 결과를 조회한다."""
    result = session.get(BenchmarkResult, benchmark_id)
    if not result or result.user_id != user_id:
        raise BenchmarkNotFound
    return result


def compare_benchmarks(
    ids: list[int], user_id: int, session: Session
) -> list[BenchmarkResult]:
    """여러 벤치마크 결과를 비교용으로 조회한다."""
    results = []
    for bid in ids:
        result = session.get(BenchmarkResult, bid)
        if not result or result.user_id != user_id:
            raise BenchmarkNotFound(f"벤치마크 #{bid}을(를) 찾을 수 없습니다")
        results.append(result)
    return results

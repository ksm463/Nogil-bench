"""처리 시간 측정 유틸리티."""

import time
from contextlib import contextmanager

from loguru import logger


@contextmanager
def timer(label: str = ""):
    """컨텍스트 매니저: 블록 실행 시간을 측정한다.

    사용법:
        with timer("blur 10장") as t:
            ...
        print(t.elapsed)
    """
    t = _TimerResult()
    start = time.perf_counter()
    try:
        yield t
    finally:
        t.elapsed = time.perf_counter() - start
        if label:
            logger.info(f"[{label}] {t.elapsed:.3f}s")


class _TimerResult:
    elapsed: float = 0.0

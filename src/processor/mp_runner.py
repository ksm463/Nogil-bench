"""multiprocessing 기반 병렬 처리 러너.

프로세스 격리로 GIL을 우회하므로 GIL 설정과 무관하게 항상 병렬 실행된다.
단, 프로세스 생성 오버헤드와 IPC(inter-process communication) 비용이 있다.

주의: ProcessPoolExecutor는 함수를 pickle로 직렬화하므로
      처리 함수가 모듈 최상위에 정의되어야 한다.
"""

import multiprocessing
from concurrent.futures import ProcessPoolExecutor

from PIL import Image

from processor import operations

# ProcessPoolExecutor가 pickle할 수 있도록 모듈 최상위에 정의
_operation: str = ""
_params: dict = {}


def _process_one(path: str) -> Image.Image:
    """단일 이미지 처리 — 모듈 최상위 함수 (pickle 호환)."""
    op_func = operations.get_operation(_operation)
    img = Image.open(path).convert("RGB")
    return op_func(img, **_params)


def _init_worker(operation: str, params: dict) -> None:
    """워커 프로세스 초기화 — 전역 변수로 설정을 전달한다."""
    global _operation, _params
    _operation = operation
    _params = params


def run(
    image_paths: list[str],
    operation: str,
    params: dict | None = None,
    workers: int = 4,
) -> list[Image.Image]:
    """ProcessPoolExecutor로 이미지를 병렬 처리한다."""
    params = params or {}

    mp_context = multiprocessing.get_context("fork")
    with ProcessPoolExecutor(
        max_workers=workers,
        mp_context=mp_context,
        initializer=_init_worker,
        initargs=(operation, params),
    ) as pool:
        results = list(pool.map(_process_one, image_paths))

    return results

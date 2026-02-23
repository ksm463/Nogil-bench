"""free-threaded (GIL=0) threading 러너.

PYTHON_GIL=0 + --disable-gil 빌드에서 threading이 진정한 병렬 처리를 달성한다.
thread_runner.py와 코드 구조는 동일하지만, 런타임에 GIL 비활성화를 검증한다.

이 러너가 존재하는 이유:
  - thread_runner: GIL=1 환경에서 threading의 한계를 보여줌
  - frethread_runner: GIL=0 환경에서 threading의 진짜 가치를 보여줌
  - 벤치마크에서 동일 코드가 GIL 설정에 따라 어떻게 달라지는지 비교
"""

import sys
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

from processor import operations


def run(
    image_paths: list[str],
    operation: str,
    params: dict | None = None,
    workers: int = 4,
) -> list[Image.Image]:
    """GIL=0 환경에서 ThreadPoolExecutor로 이미지를 진정한 병렬 처리한다."""
    if sys._is_gil_enabled():
        raise RuntimeError(
            "frethread_runner는 GIL이 비활성화된 환경에서만 사용할 수 있습니다. "
            "PYTHON_GIL=0 환경변수와 --disable-gil 빌드가 필요합니다."
        )

    op_func = getattr(operations, operation)
    params = params or {}

    def process_one(path: str) -> Image.Image:
        img = Image.open(path).convert("RGB")
        return op_func(img, **params)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(process_one, image_paths))

    return results

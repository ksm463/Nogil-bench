"""threading 기반 병렬 처리 러너.

GIL=1 환경에서의 threading 한계를 보여주기 위한 러너.
순수 Python CPU-bound 작업에서는 GIL 때문에 병렬 효과가 없고,
C 확장(Pillow 등)은 내부에서 GIL을 릴리즈하므로 병렬 효과가 있다.
"""

from concurrent.futures import ThreadPoolExecutor

from PIL import Image

from processor import operations


def run(
    image_paths: list[str],
    operation: str,
    params: dict | None = None,
    workers: int = 4,
) -> list[Image.Image]:
    """ThreadPoolExecutor로 이미지를 병렬 처리한다."""
    op_func = getattr(operations, operation)
    params = params or {}

    def process_one(path: str) -> Image.Image:
        img = Image.open(path).convert("RGB")
        return op_func(img, **params)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(process_one, image_paths))

    return results

"""동기 순차 처리 러너 (기준선)."""

from PIL import Image

from processor import operations


def run(image_paths: list[str], operation: str, params: dict | None = None) -> list[Image.Image]:
    """이미지를 순차적으로 처리한다."""
    op_func = getattr(operations, operation)
    params = params or {}
    results = []

    for path in image_paths:
        img = Image.open(path).convert("RGB")
        result = op_func(img, **params)
        results.append(result)

    return results

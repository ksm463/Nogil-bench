"""
동기 순차 처리 기준선(baseline) 벤치마크.

사용법 (컨테이너 내부):
    cd /app/src && uv run python -m scripts.bench_baseline
"""

import os
import sys

from processor.sync_runner import run
from utility.timer import timer

FIXTURES_DIR = "/app/tests/fixtures"


def main():
    image_paths = [
        os.path.join(FIXTURES_DIR, f)
        for f in sorted(os.listdir(FIXTURES_DIR))
        if f.endswith((".jpg", ".jpeg", ".png"))
    ]

    if not image_paths:
        print(f"No images found in {FIXTURES_DIR}")
        sys.exit(1)

    # 10장으로 맞추기 (4장을 반복해서 채움)
    count = 10
    images_10 = (image_paths * ((count // len(image_paths)) + 1))[:count]

    print(f"Images: {len(images_10)}장")
    print(f"GIL enabled: {sys._is_gil_enabled()}")
    print("-" * 50)

    operations = {
        "blur": {"radius": 10},
        "resize": {"width": 800, "height": 600},
        "sharpen": {},
        "grayscale": {},
        "rotate": {"degrees": 45},
        "watermark": {"text": "nogil-bench"},
    }

    for op_name, params in operations.items():
        with timer(f"sync {op_name} x{count}") as t:
            run(images_10, op_name, params)
        per_image = t.elapsed / count * 1000
        print(f"  {op_name:12s}  total={t.elapsed:.3f}s  per_image={per_image:.1f}ms")

    print("-" * 50)
    print("Baseline measurement complete")


if __name__ == "__main__":
    main()

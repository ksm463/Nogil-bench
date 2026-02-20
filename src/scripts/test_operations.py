"""
이미지 처리 함수 동작 테스트 스크립트.

사용법 (컨테이너 내부):
    cd /app/src && uv run python -m scripts.test_operations

결과물:
    tests/fixtures/output/ 에 처리된 이미지 저장
"""

import os
import sys
import time

from PIL import Image

from processor.operations import blur, grayscale, resize, rotate, sharpen, watermark

FIXTURES_DIR = "/app/tests/fixtures"
OUTPUT_DIR = "/app/tests/fixtures/output"

OPERATIONS = {
    "resize": lambda img: resize(img, 800, 600),
    "blur": lambda img: blur(img, 10),
    "sharpen": lambda img: sharpen(img),
    "grayscale": lambda img: grayscale(img),
    "rotate": lambda img: rotate(img, 45),
    "watermark": lambda img: watermark(img, "nogil-bench"),
}


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    images = [f for f in sorted(os.listdir(FIXTURES_DIR)) if f.endswith((".jpg", ".jpeg", ".png"))]

    if not images:
        print(f"No images found in {FIXTURES_DIR}")
        sys.exit(1)

    total_count = 0

    for fname in images:
        img = Image.open(os.path.join(FIXTURES_DIR, fname)).convert("RGB")
        name = os.path.splitext(fname)[0]
        print(f"=== {fname} ({img.size[0]}x{img.size[1]}) ===")

        for op_name, op_func in OPERATIONS.items():
            start = time.perf_counter()
            result = op_func(img)
            elapsed = time.perf_counter() - start

            out_path = os.path.join(OUTPUT_DIR, f"{name}_{op_name}.jpg")
            result.save(out_path, "JPEG", quality=85)
            print(f"  {op_name:12s} -> {result.size[0]}x{result.size[1]}  {elapsed * 1000:6.1f}ms")
            total_count += 1

        print()

    print(f"Done: {total_count} files saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

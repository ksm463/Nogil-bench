"""asyncio 기반 처리 러너.

핵심 실험: CPU-bound 작업에서 asyncio가 왜 도움이 안 되는지 확인.

asyncio는 I/O 대기 시간에 다른 작업을 끼워넣는 구조(협력적 멀티태스킹).
CPU를 계속 점유하는 이미지 처리에서는 양보(await) 시점이 없어서
결국 순차 실행과 동일하게 동작한다.

대안: run_in_executor()로 스레드풀에 위임하면
I/O 계층은 비동기로, 실제 처리는 스레드에서 병렬로 실행할 수 있다.
(단, GIL=1이면 스레드풀도 순차 실행됨)
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

from processor import operations


async def run(
    image_paths: list[str], operation: str, params: dict | None = None
) -> list[Image.Image]:
    """asyncio로 이미지를 처리한다.

    CPU-bound 함수를 async로 감싸도 내부에 await 포인트가 없으므로
    이벤트 루프를 블로킹하며 순차 실행된다.
    """
    op_func = getattr(operations, operation)
    params = params or {}
    results = []

    for path in image_paths:
        img = Image.open(path).convert("RGB")
        result = op_func(img, **params)
        results.append(result)
        # await asyncio.sleep(0) 을 넣어도 CPU 작업 자체는 빨라지지 않음

    return results


async def run_with_executor(
    image_paths: list[str],
    operation: str,
    params: dict | None = None,
    workers: int = 4,
) -> list[Image.Image]:
    """run_in_executor로 CPU 작업을 스레드풀에 위임한다.

    이벤트 루프가 블로킹되지 않으면서 스레드에서 병렬 실행.
    GIL=1이면 스레드가 순차 실행되고, GIL=0이면 진짜 병렬.
    """
    op_func = getattr(operations, operation)
    params = params or {}

    def process_one(path: str) -> Image.Image:
        img = Image.open(path).convert("RGB")
        return op_func(img, **params)

    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [loop.run_in_executor(pool, process_one, p) for p in image_paths]
        results = await asyncio.gather(*futures)

    return list(results)

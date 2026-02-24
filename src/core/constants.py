"""프로젝트 전역 상수 및 타입 별칭.

지원하는 이미지 처리 작업(operation)과 동시성 방식(method)의
이름 집합과 Literal 타입을 한곳에서 정의한다.

주의: Literal 타입과 set은 Python 타입 시스템의 제약으로
     자동 동기화가 불가능하므로, 값을 추가/삭제할 때 둘 다 수정해야 한다.
"""

from typing import Literal

# --- 이미지 처리 작업(operation) ---

OperationType = Literal["blur", "grayscale", "resize", "rotate", "sharpen", "watermark"]

OPERATION_NAMES: set[str] = {"blur", "grayscale", "resize", "rotate", "sharpen", "watermark"}

# --- 동시성 방식(method) ---

MethodType = Literal["sync", "threading", "multiprocessing", "frethread"]

METHOD_NAMES: set[str] = {"sync", "threading", "multiprocessing", "frethread"}

# --- operation별 기본 파라미터 ---

DEFAULT_PARAMS: dict[str, dict] = {
    "resize": {"width": 200, "height": 200},
    "blur": {"radius": 10},
}


def get_default_params(operation: str, params: dict | None) -> dict:
    """params가 비어있으면 operation에 맞는 기본값을 반환한다."""
    if params:
        return params
    return DEFAULT_PARAMS.get(operation, {})

"""벤치마크 API 라우터.

4가지 동시성 방식(sync, threading, multiprocessing, frethread)의
성능을 측정하고 결과를 저장/비교한다.
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlmodel import Session

from core.dependencies import get_current_user
from core.exceptions import ErrorResponse
from model.database import get_session
from model.user import User
from service import benchmark_service

router = APIRouter(prefix="/api/benchmarks", tags=["benchmarks"])


class BenchmarkRunRequest(BaseModel):
    method: str = Field(description="sync, threading, multiprocessing, frethread")
    operation: str = Field(default="blur", description="blur, resize, grayscale 등")
    workers: int = Field(default=4, ge=1, le=16)
    image_count: int = Field(default=10, ge=1, le=100)
    params: dict | None = None


_AUTH_401 = {"model": ErrorResponse, "description": "인증 실패 (토큰 누락/만료)"}
_NOT_FOUND_404 = {"model": ErrorResponse, "description": "벤치마크 결과를 찾을 수 없음"}


@router.post(
    "/run",
    status_code=201,
    summary="벤치마크 실행",
    description="지정한 동시성 방식(sync/threading/multiprocessing/frethread)으로 "
    "이미지 처리 벤치마크를 실행하고 결과를 DB에 저장한다.",
    responses={
        400: {"model": ErrorResponse, "description": "지원하지 않는 method 또는 operation"},
        401: _AUTH_401,
    },
)
def run_benchmark(
    req: BenchmarkRunRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return benchmark_service.run_benchmark(
        method=req.method,
        operation=req.operation,
        workers=req.workers,
        image_count=req.image_count,
        params=req.params,
        user_id=current_user.id,
        session=session,
    )


@router.get(
    "/",
    summary="벤치마크 결과 목록",
    description="현재 사용자의 벤치마크 실행 결과 목록을 반환한다.",
    responses={401: _AUTH_401},
)
def list_benchmarks(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return benchmark_service.list_benchmarks(current_user.id, session)


@router.get(
    "/compare",
    summary="벤치마크 결과 비교",
    description="여러 벤치마크 결과를 ID로 지정하여 나란히 비교한다.",
    responses={401: _AUTH_401, 404: _NOT_FOUND_404},
)
def compare_benchmarks(
    ids: list[int] = Query(description="비교할 벤치마크 ID 목록"),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return benchmark_service.compare_benchmarks(ids, current_user.id, session)


@router.get(
    "/{benchmark_id}",
    summary="벤치마크 결과 상세",
    description="벤치마크 ID로 실행 결과 상세(방식, 워커 수, 소요 시간, 이미지당 시간 등)를 조회한다.",
    responses={401: _AUTH_401, 404: _NOT_FOUND_404},
)
def get_benchmark(
    benchmark_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return benchmark_service.get_benchmark(benchmark_id, current_user.id, session)

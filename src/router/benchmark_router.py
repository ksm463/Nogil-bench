"""벤치마크 API 라우터.

4가지 동시성 방식(sync, threading, multiprocessing, frethread)의
성능을 측정하고 결과를 저장/비교한다.
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlmodel import Session

from core.dependencies import get_current_user
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


@router.post("/run", status_code=201)
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


@router.get("/")
def list_benchmarks(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return benchmark_service.list_benchmarks(current_user.id, session)


@router.get("/compare")
def compare_benchmarks(
    ids: list[int] = Query(description="비교할 벤치마크 ID 목록"),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return benchmark_service.compare_benchmarks(ids, current_user.id, session)


@router.get("/{benchmark_id}")
def get_benchmark(
    benchmark_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return benchmark_service.get_benchmark(benchmark_id, current_user.id, session)

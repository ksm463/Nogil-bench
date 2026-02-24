"""배치 처리 작업 API 라우터.

여러 이미지를 한 번에 처리하는 배치 작업을 생성하고,
작업 상태를 조회하고, 완료된 결과를 확인한다.
"""

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session

from core.dependencies import get_current_user
from core.exceptions import ErrorResponse
from model.database import get_session
from model.user import User
from service import job_service

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class BatchRequest(BaseModel):
    image_ids: list[int] = Field(min_length=1)
    operation: str = Field(default="blur")
    params: dict | None = None
    method: str = Field(default="sync")
    workers: int = Field(default=4, ge=1, le=16)


_AUTH_401 = {"model": ErrorResponse, "description": "인증 실패 (토큰 누락/만료)"}
_NOT_FOUND_404 = {"model": ErrorResponse, "description": "작업을 찾을 수 없음"}
_FORBIDDEN_403 = {"model": ErrorResponse, "description": "다른 사용자의 작업에 접근"}


@router.post(
    "/batch",
    status_code=202,
    summary="배치 작업 생성",
    description="여러 이미지를 지정한 동시성 방식으로 일괄 처리하는 작업을 생성한다. "
    "202 Accepted와 함께 job_id를 즉시 반환하고, 처리는 백그라운드에서 진행된다.",
    responses={401: _AUTH_401},
)
def create_batch_job(
    req: BatchRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    job = job_service.create_job(
        image_ids=req.image_ids,
        operation=req.operation,
        params=req.params,
        method=req.method,
        workers=req.workers,
        user_id=current_user.id,
        session=session,
    )
    background_tasks.add_task(job_service.process_job, job.id)
    return job


@router.get(
    "/",
    summary="내 작업 목록",
    description="현재 사용자의 배치 작업 목록(상태, 진행률 포함)을 반환한다.",
    responses={401: _AUTH_401},
)
def list_jobs(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return job_service.list_jobs(current_user.id, session)


@router.get(
    "/{job_id}",
    summary="작업 상태 조회",
    description="작업 ID로 상태(queued/processing/completed/failed), 진행률, 소요 시간을 조회한다.",
    responses={401: _AUTH_401, 403: _FORBIDDEN_403, 404: _NOT_FOUND_404},
)
def get_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return job_service.get_job(job_id, current_user.id, session)


@router.get(
    "/{job_id}/result",
    summary="작업 결과 조회",
    description="완료된 배치 작업의 처리 결과(소요 시간, 처리된 이미지 수 등)를 반환한다. "
    "작업이 아직 완료되지 않았으면 400 에러.",
    responses={
        400: {"model": ErrorResponse, "description": "작업이 아직 완료되지 않음"},
        401: _AUTH_401,
        403: _FORBIDDEN_403,
        404: _NOT_FOUND_404,
    },
)
def get_job_result(
    job_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return job_service.get_job_result(job_id, current_user.id, session)

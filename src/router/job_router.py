"""배치 처리 작업 API 라우터.

여러 이미지를 한 번에 처리하는 배치 작업을 생성하고,
작업 상태를 조회하고, 완료된 결과를 확인한다.
"""

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session

from core.dependencies import get_current_user
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


@router.post("/batch", status_code=202)
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


@router.get("/")
def list_jobs(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return job_service.list_jobs(current_user.id, session)


@router.get("/{job_id}")
def get_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return job_service.get_job(job_id, current_user.id, session)


@router.get("/{job_id}/result")
def get_job_result(
    job_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return job_service.get_job_result(job_id, current_user.id, session)

"""배치 처리 작업 서비스.

BackgroundTasks를 통해 비동기로 이미지를 처리하고,
Job 레코드에 진행률과 상태를 업데이트한다.
"""

import json
import os
import time
from datetime import UTC, datetime

from PIL import Image
from sqlmodel import Session, select

from core.config import settings
from core.constants import METHOD_NAMES, OPERATION_NAMES, get_default_params
from core.exceptions import (
    Forbidden,
    ImageNotFound,
    InvalidMethod,
    InvalidOperation,
    JobNotCompleted,
    JobNotFound,
)
from model.database import engine as default_engine
from model.image import ImageRecord
from model.job import Job
from processor import operations

# BackgroundTasks에서 사용할 엔진. 테스트 시 오버라이드 가능.
_engine = None


def get_engine():
    return _engine or default_engine


def create_job(
    image_ids: list[int],
    operation: str,
    params: dict | None,
    method: str,
    workers: int,
    user_id: int,
    session: Session,
) -> Job:
    """배치 작업을 생성한다. 이미지 소유권을 검증하고 Job 레코드를 DB에 저장."""
    if method not in METHOD_NAMES:
        raise InvalidMethod(f"지원하지 않는 방식: {method}")
    if operation not in OPERATION_NAMES:
        raise InvalidOperation(f"지원하지 않는 작업: {operation}")

    # 이미지 소유권 검증
    for iid in image_ids:
        record = session.get(ImageRecord, iid)
        if not record:
            raise ImageNotFound(f"이미지 #{iid}을(를) 찾을 수 없습니다")
        if record.user_id != user_id:
            raise Forbidden(f"이미지 #{iid}에 대한 접근 권한이 없습니다")

    job = Job(
        user_id=user_id,
        operation=operation,
        params=json.dumps(params or {}),
        method=method,
        workers=workers,
        image_ids=json.dumps(image_ids),
        image_count=len(image_ids),
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def process_job(job_id: int) -> None:
    """백그라운드에서 배치 작업을 실행한다.

    별도 세션을 열어 작업 상태를 업데이트한다.
    BackgroundTasks에서 호출되므로 요청 세션과 분리되어야 한다.
    """
    with Session(get_engine()) as session:
        job = session.get(Job, job_id)
        if not job:
            return

        job.status = "processing"
        session.commit()

        image_ids = job.image_id_list
        params = job.params_dict
        try:
            op_func = operations.get_operation(job.operation)
        except ValueError as e:
            job.status = "failed"
            job.error_message = str(e)
            session.commit()
            return

        params = get_default_params(job.operation, params)

        os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
        start = time.perf_counter()

        try:
            for iid in image_ids:
                record = session.get(ImageRecord, iid)
                if not record:
                    continue

                img = Image.open(record.original_path).convert("RGB")
                result = op_func(img, **params)

                name = os.path.splitext(os.path.basename(record.original_path))[0]
                output_name = f"{name}_{job.operation}_job{job.id}.jpg"
                output_path = os.path.join(settings.OUTPUT_DIR, output_name)
                result.save(output_path, "JPEG", quality=85)

                record.output_path = output_path
                record.operation = job.operation
                record.status = "completed"

                job.processed_count += 1
                session.commit()

            job.status = "completed"
        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)

        job.duration = round(time.perf_counter() - start, 4)
        job.completed_at = datetime.now(UTC)
        session.commit()


def list_jobs(user_id: int, session: Session) -> list[Job]:
    """해당 사용자의 작업 목록을 반환한다."""
    return list(
        session.exec(
            select(Job).where(Job.user_id == user_id).order_by(Job.created_at.desc())
        ).all()
    )


def get_job(job_id: int, user_id: int, session: Session) -> Job:
    """작업 상태를 조회한다."""
    job = session.get(Job, job_id)
    if not job or job.user_id != user_id:
        raise JobNotFound
    return job


def get_job_result(job_id: int, user_id: int, session: Session) -> list[ImageRecord]:
    """완료된 작업의 처리된 이미지 목록을 반환한다."""
    job = get_job(job_id, user_id, session)
    if job.status != "completed":
        raise JobNotCompleted(f"작업이 아직 완료되지 않았습니다 (현재: {job.status})")

    return list(
        session.exec(
            select(ImageRecord).where(ImageRecord.id.in_(job.image_id_list))
        ).all()
    )

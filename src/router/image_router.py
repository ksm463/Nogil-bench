from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session

from core.dependencies import get_current_user
from core.exceptions import ErrorResponse, ImageNotProcessed
from model.database import get_session
from model.user import User
from service import image_service

router = APIRouter(prefix="/api/images", tags=["images"])


class ProcessRequest(BaseModel):
    operation: str
    params: dict = {}


_AUTH_401 = {"model": ErrorResponse, "description": "인증 실패 (토큰 누락/만료)"}
_NOT_FOUND_404 = {"model": ErrorResponse, "description": "이미지를 찾을 수 없음"}
_FORBIDDEN_403 = {"model": ErrorResponse, "description": "다른 사용자의 이미지에 접근"}


@router.post(
    "/upload",
    summary="이미지 업로드",
    description="이미지 파일을 업로드하고 DB에 메타데이터를 저장한다.",
    responses={401: _AUTH_401, 422: {"description": "파일 형식 오류"}},
)
def upload_image(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return image_service.save_upload(file, current_user.id, session)


@router.get(
    "/",
    summary="내 이미지 목록",
    description="현재 사용자가 업로드한 이미지 목록을 반환한다.",
    responses={401: _AUTH_401},
)
def list_images(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return image_service.list_images(current_user.id, session)


@router.get(
    "/{image_id}",
    summary="이미지 상세 조회",
    description="이미지 ID로 메타데이터(파일명, 처리 상태, 경로 등)를 조회한다.",
    responses={401: _AUTH_401, 403: _FORBIDDEN_403, 404: _NOT_FOUND_404},
)
def get_image(
    image_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return image_service.get_image_or_raise(image_id, current_user.id, session)


@router.post(
    "/{image_id}/process",
    summary="이미지 처리",
    description="지정한 이미지에 처리 작업(blur, resize, grayscale 등)을 적용한다.",
    responses={
        400: {"model": ErrorResponse, "description": "지원하지 않는 작업(operation)"},
        401: _AUTH_401,
        403: _FORBIDDEN_403,
        404: _NOT_FOUND_404,
    },
)
def process_image(
    image_id: int,
    req: ProcessRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return image_service.process_image(
        image_id, req.operation, req.params, current_user.id, session
    )


@router.get(
    "/{image_id}/download",
    summary="처리된 이미지 다운로드",
    description="처리가 완료된 이미지 파일을 다운로드한다. 미처리 시 400 에러.",
    responses={
        400: {"model": ErrorResponse, "description": "아직 처리되지 않은 이미지"},
        401: _AUTH_401,
        403: _FORBIDDEN_403,
        404: _NOT_FOUND_404,
    },
)
def download_image(
    image_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    record = image_service.get_image_or_raise(image_id, current_user.id, session)
    if not record.output_path:
        raise ImageNotProcessed
    return FileResponse(record.output_path, filename=f"{record.filename}")


@router.delete(
    "/{image_id}",
    summary="이미지 삭제",
    description="이미지 메타데이터와 파일을 삭제한다.",
    responses={401: _AUTH_401, 403: _FORBIDDEN_403, 404: _NOT_FOUND_404},
)
def delete_image(
    image_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    image_service.delete_image(image_id, current_user.id, session)
    return {"detail": "Deleted"}

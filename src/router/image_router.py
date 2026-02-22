from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session

from core.dependencies import get_current_user
from core.exceptions import ImageNotProcessed
from model.database import get_session
from model.user import User
from service import image_service

router = APIRouter(prefix="/api/images", tags=["images"])


class ProcessRequest(BaseModel):
    operation: str
    params: dict = {}


@router.post("/upload")
def upload_image(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return image_service.save_upload(file, current_user.id, session)


@router.get("/")
def list_images(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return image_service.list_images(current_user.id, session)


@router.get("/{image_id}")
def get_image(
    image_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return image_service.get_image_or_raise(image_id, current_user.id, session)


@router.post("/{image_id}/process")
def process_image(
    image_id: int,
    req: ProcessRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    return image_service.process_image(
        image_id, req.operation, req.params, current_user.id, session
    )


@router.get("/{image_id}/download")
def download_image(
    image_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    record = image_service.get_image_or_raise(image_id, current_user.id, session)
    if not record.output_path:
        raise ImageNotProcessed
    return FileResponse(record.output_path, filename=f"{record.filename}")


@router.delete("/{image_id}")
def delete_image(
    image_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    image_service.delete_image(image_id, current_user.id, session)
    return {"detail": "Deleted"}

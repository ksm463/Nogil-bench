from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session

from model.database import get_session
from service import image_service

router = APIRouter(prefix="/api/images", tags=["images"])


class ProcessRequest(BaseModel):
    operation: str
    params: dict = {}


@router.post("/upload")
def upload_image(file: UploadFile, session: Session = Depends(get_session)):
    return image_service.save_upload(file, session)


@router.get("/")
def list_images(session: Session = Depends(get_session)):
    return image_service.list_images(session)


@router.get("/{image_id}")
def get_image(image_id: int, session: Session = Depends(get_session)):
    record = image_service.get_image(image_id, session)
    if not record:
        raise HTTPException(status_code=404, detail="Image not found")
    return record


@router.post("/{image_id}/process")
def process_image(
    image_id: int, req: ProcessRequest, session: Session = Depends(get_session)
):
    try:
        record = image_service.process_image(image_id, req.operation, req.params, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not record:
        raise HTTPException(status_code=404, detail="Image not found")
    return record


@router.get("/{image_id}/download")
def download_image(image_id: int, session: Session = Depends(get_session)):
    record = image_service.get_image(image_id, session)
    if not record:
        raise HTTPException(status_code=404, detail="Image not found")
    if not record.output_path:
        raise HTTPException(status_code=400, detail="Image not processed yet")
    return FileResponse(record.output_path, filename=f"{record.filename}")


@router.delete("/{image_id}")
def delete_image(image_id: int, session: Session = Depends(get_session)):
    if not image_service.delete_image(image_id, session):
        raise HTTPException(status_code=404, detail="Image not found")
    return {"detail": "Deleted"}

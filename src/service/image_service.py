import os
import uuid

from fastapi import UploadFile
from PIL import Image
from sqlmodel import Session, select

from core.config import settings
from core.exceptions import Forbidden, ImageNotFound, InvalidOperation
from model.image import ImageRecord
from processor.operations import blur, grayscale, resize, rotate, sharpen, watermark

OPERATIONS = {
    "resize": resize,
    "blur": blur,
    "sharpen": sharpen,
    "grayscale": grayscale,
    "rotate": rotate,
    "watermark": watermark,
}


def save_upload(file: UploadFile, user_id: int, session: Session) -> ImageRecord:
    """파일을 디스크에 저장하고 DB에 기록한다."""
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    ext = os.path.splitext(file.filename or "image.jpg")[1]
    saved_name = f"{uuid.uuid4().hex}{ext}"
    saved_path = os.path.join(settings.UPLOAD_DIR, saved_name)

    with open(saved_path, "wb") as f:
        f.write(file.file.read())

    record = ImageRecord(
        filename=file.filename or "unknown",
        original_path=saved_path,
        user_id=user_id,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def list_images(user_id: int, session: Session) -> list[ImageRecord]:
    """해당 사용자의 이미지 목록만 반환한다."""
    return list(
        session.exec(
            select(ImageRecord).where(ImageRecord.user_id == user_id)
        ).all()
    )


def get_image_or_raise(image_id: int, user_id: int, session: Session) -> ImageRecord:
    """ID로 이미지를 조회하고, 소유권을 검증한다.

    - 이미지가 없으면 None 대신 구분 가능한 예외를 발생시킨다.
    - 다른 사용자의 이미지면 PermissionError를 발생시킨다.
    """
    record = session.get(ImageRecord, image_id)
    if not record:
        raise ImageNotFound
    if record.user_id != user_id:
        raise Forbidden
    return record


def process_image(
    image_id: int, operation: str, params: dict, user_id: int, session: Session
) -> ImageRecord:
    """이미지에 처리를 적용하고 결과를 저장한다."""
    record = get_image_or_raise(image_id, user_id, session)

    op_func = OPERATIONS.get(operation)
    if not op_func:
        raise InvalidOperation(f"지원하지 않는 작업: {operation}")

    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)

    record.status = "processing"
    session.commit()

    img = Image.open(record.original_path).convert("RGB")
    result = op_func(img, **params)

    name = os.path.splitext(os.path.basename(record.original_path))[0]
    output_name = f"{name}_{operation}.jpg"
    output_path = os.path.join(settings.OUTPUT_DIR, output_name)
    result.save(output_path, "JPEG", quality=85)

    record.output_path = output_path
    record.operation = operation
    record.status = "completed"
    session.commit()
    session.refresh(record)
    return record


def delete_image(image_id: int, user_id: int, session: Session) -> bool:
    """이미지 레코드와 파일을 삭제한다."""
    record = get_image_or_raise(image_id, user_id, session)

    for path in [record.original_path, record.output_path]:
        if path and os.path.exists(path):
            os.remove(path)

    session.delete(record)
    session.commit()
    return True

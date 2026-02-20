import os
import uuid

from fastapi import UploadFile
from PIL import Image
from sqlmodel import Session, select

from core.config import settings
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


def save_upload(file: UploadFile, session: Session) -> ImageRecord:
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
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def list_images(session: Session) -> list[ImageRecord]:
    """이미지 목록을 반환한다."""
    return list(session.exec(select(ImageRecord)).all())


def get_image(image_id: int, session: Session) -> ImageRecord | None:
    """ID로 이미지를 조회한다."""
    return session.get(ImageRecord, image_id)


def process_image(
    image_id: int, operation: str, params: dict, session: Session
) -> ImageRecord | None:
    """이미지에 처리를 적용하고 결과를 저장한다."""
    record = session.get(ImageRecord, image_id)
    if not record:
        return None

    op_func = OPERATIONS.get(operation)
    if not op_func:
        raise ValueError(f"Unknown operation: {operation}")

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


def delete_image(image_id: int, session: Session) -> bool:
    """이미지 레코드와 파일을 삭제한다."""
    record = session.get(ImageRecord, image_id)
    if not record:
        return False

    for path in [record.original_path, record.output_path]:
        if path and os.path.exists(path):
            os.remove(path)

    session.delete(record)
    session.commit()
    return True

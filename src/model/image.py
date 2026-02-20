from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class ImageRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    filename: str
    original_path: str
    output_path: str | None = None
    operation: str | None = None
    status: str = Field(default="uploaded")  # uploaded, processing, completed, failed
    user_id: int | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

import json
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class Job(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    status: str = Field(default="queued")  # queued, processing, completed, failed
    method: str = Field(default="sync")  # sync, threading, multiprocessing, frethread
    operation: str  # blur, resize, grayscale, ...
    params: str = Field(default="{}")  # JSON string
    workers: int = Field(default=4)
    image_ids: str  # JSON string: [1, 2, 3]
    image_count: int
    processed_count: int = Field(default=0)
    duration: float | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    @property
    def image_id_list(self) -> list[int]:
        return json.loads(self.image_ids)

    @property
    def params_dict(self) -> dict:
        return json.loads(self.params)

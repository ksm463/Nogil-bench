from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


class BenchmarkResult(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    method: str  # sync, threading, multiprocessing, frethread
    operation: str  # blur, resize, grayscale, ...
    workers: int = Field(default=1)
    image_count: int
    duration: float  # seconds
    gil_enabled: bool
    user_id: int | None = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

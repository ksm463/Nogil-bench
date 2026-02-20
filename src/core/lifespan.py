from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from core.config import settings
from model.database import create_db_and_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    # === 시작 ===
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Python {settings.python_version} (free-threaded: {settings.gil_disabled})")
    logger.info(f"GIL enabled: {settings.gil_enabled}")

    create_db_and_tables()
    logger.info(f"Database ready ({settings.DATABASE_URL})")

    app.state.settings = settings

    yield

    # === 종료 ===
    logger.info("Shutting down")

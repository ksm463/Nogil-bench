import sys
import sysconfig

import uvicorn
from fastapi import FastAPI

from core.config import settings
from core.lifespan import lifespan

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Free-threaded Python backend benchmark — 4가지 동시성 모델 비교",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "python_version": settings.python_version,
        "free_threaded": settings.gil_disabled,
        "gil_enabled": settings.gil_enabled,
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=True)

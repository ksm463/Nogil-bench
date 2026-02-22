import uvicorn
from fastapi import FastAPI

from core.config import settings
from core.error_handlers import app_exception_handler
from core.exceptions import AppException
from core.lifespan import lifespan
from core.middleware import RequestLoggingMiddleware
from router.auth_router import router as auth_router
from router.image_router import router as image_router
import model.user  # noqa: F401 — 테이블 등록
import model.image  # noqa: F401 — 테이블 등록

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Free-threaded Python backend benchmark — 4가지 동시성 모델 비교",
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)
app.add_exception_handler(AppException, app_exception_handler)

app.include_router(auth_router)
app.include_router(image_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "python_version": settings.python_version,
        "free_threaded": settings.gil_disabled,
        "gil_enabled": settings.gil_enabled,
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        access_log=False,
    )

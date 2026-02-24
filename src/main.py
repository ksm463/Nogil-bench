import uvicorn
from fastapi import FastAPI

import model.benchmark  # noqa: F401 — 테이블 등록
import model.image  # noqa: F401 — 테이블 등록
import model.job  # noqa: F401 — 테이블 등록
import model.user  # noqa: F401 — 테이블 등록
from core.config import settings
from core.error_handlers import app_exception_handler
from core.exceptions import AppException
from core.lifespan import lifespan
from core.middleware import RequestLoggingMiddleware
from router.auth_router import router as auth_router
from router.benchmark_router import router as benchmark_router
from router.image_router import router as image_router
from router.job_router import router as job_router

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Free-threaded Python(3.14t, GIL=0) 백엔드 벤치마크 프로젝트.\n\n"
        "이미지 프로세싱 API를 통해 4가지 동시성 모델"
        "(sync, threading, multiprocessing, free-threaded)의 성능을 비교한다.\n\n"
        "**주요 기능:**\n"
        "- JWT 인증 (회원가입/로그인)\n"
        "- 이미지 업로드, 처리(blur, resize, grayscale 등), 다운로드\n"
        "- 배치 작업 생성 및 백그라운드 처리\n"
        "- 벤치마크 실행 및 결과 비교"
    ),
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)
app.add_exception_handler(AppException, app_exception_handler)

app.include_router(auth_router)
app.include_router(image_router)
app.include_router(benchmark_router)
app.include_router(job_router)


@app.get(
    "/health",
    tags=["system"],
    summary="헬스체크",
    description="서버 상태, Python 버전, GIL 활성화 여부를 반환한다.",
)
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

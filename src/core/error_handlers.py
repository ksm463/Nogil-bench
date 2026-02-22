"""전역 예외 핸들러.

AppException 계열 예외를 잡아 일관된 JSON 응답으로 변환한다.
main.py에서 app.add_exception_handler()로 등록한다.
"""

from fastapi import Request
from fastapi.responses import JSONResponse

from core.exceptions import AppException


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
        },
    )

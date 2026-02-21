import time

from fastapi import Request, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

SLOW_THRESHOLD_MS = 500


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """모든 HTTP 요청을 로깅하는 미들웨어.

    기록 항목: 메서드, 경로, 클라이언트 IP, 상태코드, 처리시간(ms)
    처리시간이 500ms를 초과하면 WARNING 레벨로 기록.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start) * 1000
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path
        status = response.status_code

        if elapsed_ms > SLOW_THRESHOLD_MS:
            logger.warning(
                f"{method} {path} | {client_ip} | {status} | {elapsed_ms:.0f}ms (slow)"
            )
        else:
            logger.info(
                f"{method} {path} | {client_ip} | {status} | {elapsed_ms:.0f}ms"
            )

        return response

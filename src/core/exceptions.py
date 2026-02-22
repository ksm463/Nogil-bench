"""앱 전역 커스텀 예외 클래스.

AppException을 상속하면 전역 핸들러(error_handlers.py)가 자동으로
{"error_code": "...", "message": "..."} 형식의 JSON 응답을 생성한다.
"""


class AppException(Exception):
    """앱 전역 베이스 예외.

    서브클래스에서 status_code, error_code, message를 클래스 변수로 정의하면
    전역 핸들러가 해당 값을 읽어 HTTP 응답을 생성한다.
    """

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "서버 내부 오류가 발생했습니다"

    def __init__(self, message: str | None = None):
        if message:
            self.message = message
        super().__init__(self.message)


# --- 인증 관련 ---


class DuplicateEmail(AppException):
    status_code = 409
    error_code = "DUPLICATE_EMAIL"
    message = "이미 등록된 이메일입니다"


class InvalidCredentials(AppException):
    status_code = 401
    error_code = "INVALID_CREDENTIALS"
    message = "이메일 또는 패스워드가 올바르지 않습니다"


class InvalidToken(AppException):
    status_code = 401
    error_code = "INVALID_TOKEN"
    message = "유효하지 않거나 만료된 토큰입니다"


# --- 이미지 관련 ---


class ImageNotFound(AppException):
    status_code = 404
    error_code = "IMAGE_NOT_FOUND"
    message = "이미지를 찾을 수 없습니다"


class Forbidden(AppException):
    status_code = 403
    error_code = "FORBIDDEN"
    message = "접근 권한이 없습니다"


class InvalidOperation(AppException):
    status_code = 400
    error_code = "INVALID_OPERATION"
    message = "지원하지 않는 이미지 처리 작업입니다"


class ImageNotProcessed(AppException):
    status_code = 400
    error_code = "IMAGE_NOT_PROCESSED"
    message = "아직 처리되지 않은 이미지입니다"

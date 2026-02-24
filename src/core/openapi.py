"""커스텀 OpenAPI 스키마 생성.

JWT Bearer 인증 스키마를 추가하여 Swagger UI에서
Authorize 버튼으로 토큰을 입력할 수 있게 한다.
"""

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def create_custom_openapi(app: FastAPI):
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            contact=app.contact,
            license_info=app.license_info,
        )

        openapi_schema["components"]["securitySchemes"] = {
            "HTTPBearer": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": (
                    "POST /auth/login으로 발급받은 JWT 토큰을 입력하세요."
                ),
            }
        }

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    return custom_openapi

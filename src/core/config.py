import sys
import sysconfig

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 앱 설정
    APP_NAME: str = "nogil-bench"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # 서버 설정
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # DB 설정 (Day 2: SQLite → Day 6: PostgreSQL)
    DATABASE_URL: str = "sqlite:///./nogil_bench.db"

    # 파일 저장 경로
    UPLOAD_DIR: str = "/app/uploads"
    OUTPUT_DIR: str = "/app/outputs"

    # JWT 설정
    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 30

    # Python 환경 정보 (읽기 전용, 환경에서 자동 감지)
    @property
    def python_version(self) -> str:
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    @property
    def gil_disabled(self) -> bool:
        return sysconfig.get_config_var("Py_GIL_DISABLED") == 1

    @property
    def gil_enabled(self) -> bool:
        return sys._is_gil_enabled()

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

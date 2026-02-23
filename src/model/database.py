"""데이터베이스 엔진 설정.

SQLite와 PostgreSQL을 모두 지원한다.
DATABASE_URL 환경변수로 어떤 DB를 쓸지 결정된다.

SQLite:
  - 파일 레벨 잠금 → 동시 쓰기에 약함
  - check_same_thread=False 필요 (FastAPI가 여러 스레드에서 접근)

PostgreSQL:
  - MVCC → 동시 쓰기 가능
  - 커넥션 풀 설정이 중요:
    * pool_size: 풀에 상시 유지하는 커넥션 수 (기본 5)
    * max_overflow: 풀이 꽉 찼을 때 추가로 열 수 있는 수 (기본 10)
    * pool_pre_ping: 커넥션 사용 전 살아있는지 확인 (네트워크 끊김 대비)
    * pool_recycle: N초 후 커넥션 재생성 (DB의 idle timeout 대비)
"""

from sqlmodel import SQLModel, Session, create_engine

from core.config import settings


def _build_engine():
    """DATABASE_URL에 따라 적절한 엔진을 생성한다."""
    url = settings.DATABASE_URL

    if url.startswith("sqlite"):
        # SQLite: check_same_thread=False만 설정
        # (풀링은 SQLite에서 의미 없음 — 파일 하나를 직접 접근)
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=settings.DB_ECHO,
        )

    # PostgreSQL (또는 다른 서버 기반 DB)
    # 커넥션 풀이 핵심 — 매 요청마다 커넥션을 새로 여는 비용을 줄인다
    return create_engine(
        url,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_pre_ping=True,     # 사용 전 커넥션 유효성 확인
        pool_recycle=300,       # 5분 후 커넥션 재생성
        echo=settings.DB_ECHO,
    )


engine = _build_engine()


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session

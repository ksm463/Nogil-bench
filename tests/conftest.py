"""pytest 공용 fixture.

모든 API 테스트는 in-memory SQLite DB를 사용하여 격리된다.
- client: TestClient (인증 없음)
- auth_headers: 회원가입 + 로그인한 유저의 Authorization 헤더
- second_user_headers: 소유권 테스트용 두 번째 유저 헤더
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

# src/ 디렉토리를 import path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from main import app
from model.database import get_session


@pytest.fixture()
def session():
    """테스트마다 새 in-memory SQLite DB를 생성한다.

    StaticPool을 사용해야 모든 커넥션이 같은 in-memory DB를 공유한다.
    (기본값은 커넥션마다 별도 DB가 생성되어 테이블이 안 보임)
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture()
def client(session):
    """get_session을 테스트용 세션으로 오버라이드한 TestClient."""

    def _override():
        yield session

    app.dependency_overrides[get_session] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _register_and_login(client: TestClient, email: str, password: str) -> dict:
    """유저를 가입시키고 로그인하여 Authorization 헤더를 반환한다."""
    client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )
    resp = client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def auth_headers(client):
    """첫 번째 테스트 유저의 인증 헤더."""
    return _register_and_login(client, "user1@test.com", "pass1234")


@pytest.fixture()
def second_user_headers(client):
    """두 번째 테스트 유저의 인증 헤더 (소유권 테스트용)."""
    return _register_and_login(client, "user2@test.com", "pass5678")

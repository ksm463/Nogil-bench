"""JWT 토큰 + bcrypt 패스워드 해싱 단위 테스트."""

from datetime import timedelta

from core.security import (
    create_access_token,
    hash_password,
    verify_password,
    verify_token,
)


def test_hash_and_verify_password():
    """bcrypt 해싱 후 원본 평문으로 검증할 수 있다."""
    plain = "mysecretpassword"
    hashed = hash_password(plain)

    assert hashed != plain
    assert verify_password(plain, hashed) is True
    assert verify_password("wrongpassword", hashed) is False


def test_create_and_verify_token():
    """JWT 생성 → 디코딩 → sub 값이 일치한다."""
    email = "test@example.com"
    token = create_access_token({"sub": email})
    payload = verify_token(token)

    assert payload is not None
    assert payload["sub"] == email
    assert "exp" in payload


def test_expired_token():
    """만료된 토큰은 verify_token이 None을 반환한다."""
    token = create_access_token(
        {"sub": "test@example.com"},
        expires_delta=timedelta(seconds=-1),
    )
    assert verify_token(token) is None

from datetime import UTC, datetime, timedelta

import jwt
from pwdlib.hashers.bcrypt import BcryptHasher

from core.config import settings

# --- 패스워드 해싱 ---
# pwdlib은 passlib의 후속 라이브러리 (Python 3.14+ 호환)
# bcrypt: 의도적으로 느린 해시 → 브루트포스 공격에 강함
pwd_hash = BcryptHasher()


def hash_password(plain: str) -> str:
    """평문 패스워드 → bcrypt 해시."""
    return pwd_hash.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """평문과 해시를 비교한다."""
    return pwd_hash.verify(plain, hashed)


# --- JWT 토큰 ---
# JWT = Header.Payload.Signature (Base64 인코딩된 3개 파트)
#
# Header:    {"alg": "HS256", "typ": "JWT"}
# Payload:   {"sub": "user@email.com", "exp": 1708500000, ...}
# Signature: HMAC-SHA256(header + payload, SECRET_KEY)
#
# 서버만 SECRET_KEY를 알고 있으므로 → 서명 위조 불가능
# 하지만 Payload는 누구나 디코딩 가능 → 비밀번호 같은 민감정보 넣지 않기


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """JWT 액세스 토큰을 생성한다.

    Args:
        data: 토큰에 담을 데이터 (보통 {"sub": email})
        expires_delta: 만료 시간. None이면 설정값 사용.
    """
    payload = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    )
    payload["exp"] = expire
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str) -> dict | None:
    """JWT 토큰을 검증하고 payload를 반환한다.

    유효하지 않거나 만료된 토큰이면 None을 반환.
    """
    try:
        return jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.PyJWTError:
        return None

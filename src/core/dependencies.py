from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from core.security import verify_token
from model.database import get_session
from model.user import User

# OAuth2PasswordBearer:
# - Swagger UI에 "Authorize" 버튼을 자동 생성
# - 요청 헤더에서 "Authorization: Bearer <token>"을 추출
# - tokenUrl은 Swagger에서 로그인할 때 호출할 엔드포인트
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    """JWT 토큰에서 현재 사용자를 추출한다.

    흐름:
    1. OAuth2PasswordBearer가 헤더에서 토큰 추출
    2. verify_token으로 서명 검증 + 만료 확인
    3. payload["sub"] (이메일)로 DB에서 사용자 조회
    4. 실패 시 401 Unauthorized
    """
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email: str | None = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )

    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user

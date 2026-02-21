from sqlmodel import Session, select

from core.security import create_access_token, hash_password, verify_password
from model.user import User


def register(email: str, password: str, session: Session) -> User:
    """새 사용자를 등록한다.

    1. 이메일 중복 확인
    2. 패스워드를 bcrypt로 해싱 (평문 저장 절대 금지)
    3. DB에 저장
    """
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        raise ValueError("이미 등록된 이메일입니다")

    user = User(
        email=email,
        hashed_password=hash_password(password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def login(email: str, password: str, session: Session) -> str | None:
    """이메일/패스워드를 확인하고 JWT를 반환한다.

    1. 이메일로 사용자 조회
    2. bcrypt로 패스워드 비교 (해시끼리 비교, 평문 비교 아님)
    3. 일치하면 JWT 생성 → sub에 이메일을 넣음
    """
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return create_access_token({"sub": user.email})

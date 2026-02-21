from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlmodel import Session

from core.dependencies import get_current_user
from model.database import get_session
from model.user import User
from service import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


# --- 요청/응답 스키마 ---

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterResponse(BaseModel):
    id: int
    email: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str


# --- 엔드포인트 ---

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, session: Session = Depends(get_session)):
    """회원가입: 이메일 + 패스워드 → 사용자 생성."""
    try:
        user = auth_service.register(req.email, req.password, session)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return RegisterResponse(id=user.id, email=user.email)


@router.post("/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    """로그인: 이메일 + 패스워드 → JWT 토큰 반환.

    OAuth2PasswordRequestForm을 사용하는 이유:
    - Swagger UI의 Authorize 버튼과 자동 연동
    - form.username에 이메일을 넣음 (OAuth2 표준 필드명이 username)
    """
    token = auth_service.login(form.username, form.password, session)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 패스워드가 올바르지 않습니다",
        )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """현재 로그인한 사용자 정보 조회. (토큰 필수)"""
    return UserResponse(id=current_user.id, email=current_user.email)

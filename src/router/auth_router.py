from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import Session

from core.dependencies import get_current_user
from core.exceptions import ErrorResponse
from model.database import get_session
from model.user import User
from service import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


# --- 요청/응답 스키마 ---

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="최소 8자 이상")


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

@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회원가입",
    description="이메일과 패스워드로 새 사용자를 생성한다. 패스워드는 bcrypt로 해싱되어 저장된다.",
    responses={
        409: {"model": ErrorResponse, "description": "이미 등록된 이메일"},
        422: {"description": "요청 형식 오류 (이메일 형식 등)"},
    },
)
def register(req: RegisterRequest, session: Session = Depends(get_session)):
    user = auth_service.register(req.email, req.password, session)
    return RegisterResponse(id=user.id, email=user.email)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="로그인",
    description="이메일과 패스워드로 인증 후 JWT 액세스 토큰을 반환한다. "
    "Swagger UI의 Authorize 버튼과 연동되는 OAuth2 폼을 사용한다.",
    responses={
        401: {"model": ErrorResponse, "description": "이메일 또는 패스워드 불일치"},
    },
)
def login(form: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    token = auth_service.login(form.username, form.password, session)
    return TokenResponse(access_token=token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="내 정보 조회",
    description="현재 로그인한 사용자의 ID와 이메일을 반환한다. JWT 토큰 필수.",
    responses={
        401: {"model": ErrorResponse, "description": "토큰 누락 또는 만료"},
    },
)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(id=current_user.id, email=current_user.email)

# Day 4 진행 기록

> 날짜: 2026-02-22 (토)
> 단계: 커스텀 에러 핸들링 + pytest 테스트 스위트 + 동시성 벤치마크

---

## 1. 커스텀 예외 + 전역 에러 핸들러

### Before → After

```
# Before (FastAPI 기본):
422 {"detail": [{"loc": ["body", "email"], "msg": "field required", ...}]}
404 {"detail": "Image not found"}
403 {"detail": "Access denied"}

# After (커스텀):
409 {"error_code": "DUPLICATE_EMAIL", "message": "이미 등록된 이메일입니다"}
404 {"error_code": "IMAGE_NOT_FOUND", "message": "이미지를 찾을 수 없습니다"}
403 {"error_code": "FORBIDDEN", "message": "접근 권한이 없습니다"}
```

### 생성된 파일

```
src/core/
├── exceptions.py        # ★ NEW — 커스텀 예외 클래스 (AppException 상속 체계)
├── error_handlers.py    # ★ NEW — 전역 예외 핸들러
```

### 예외 클래스 계층

```python
AppException                # 베이스 (status_code, error_code, message)
├── DuplicateEmail          # 409 DUPLICATE_EMAIL
├── InvalidCredentials      # 401 INVALID_CREDENTIALS
├── InvalidToken            # 401 INVALID_TOKEN
├── ImageNotFound           # 404 IMAGE_NOT_FOUND
├── Forbidden               # 403 FORBIDDEN
├── InvalidOperation        # 400 INVALID_OPERATION
└── ImageNotProcessed       # 400 IMAGE_NOT_PROCESSED
```

### 전역 핸들러 동작 방식

```python
# core/error_handlers.py
async def app_exception_handler(request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error_code": exc.error_code, "message": exc.message},
    )

# main.py에서 등록
app.add_exception_handler(AppException, app_exception_handler)
```

- 서비스 레이어에서 `raise ImageNotFound` → 전역 핸들러가 자동으로 404 JSON 응답 생성
- 라우터의 `try-except` 블록이 전부 제거되어 코드가 깔끔해짐

### 수정된 파일

| 파일 | 변경 내용 |
|------|----------|
| `service/auth_service.py` | `ValueError` → `DuplicateEmail`, `return None` → `raise InvalidCredentials` |
| `service/image_service.py` | `LookupError` → `ImageNotFound`, `PermissionError` → `Forbidden`, `ValueError` → `InvalidOperation` |
| `router/image_router.py` | try-except 블록 4개 전부 제거 |
| `router/auth_router.py` | try-except 블록 제거, `if not token` 분기 제거 |
| `core/dependencies.py` | `HTTPException(401)` 3곳 → `InvalidToken` |
| `main.py` | `app.add_exception_handler()` 추가 |

### 라우터 Before → After 비교

```python
# Before — 모든 엔드포인트마다 같은 try-except 반복
@router.get("/{image_id}")
def get_image(image_id: int, ...):
    try:
        return image_service.get_image_or_raise(image_id, current_user.id, session)
    except LookupError:
        raise HTTPException(status_code=404, detail="Image not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Access denied")

# After — 서비스가 AppException을 발생시키면 전역 핸들러가 자동 처리
@router.get("/{image_id}")
def get_image(image_id: int, ...):
    return image_service.get_image_or_raise(image_id, current_user.id, session)
```

---

## 2. pytest 테스트 스위트

### 생성된 파일

```
tests/
├── __init__.py
├── conftest.py              # ★ NEW — 공용 fixture (client, auth_headers 등)
├── test_security.py         # ★ NEW — JWT + bcrypt 단위 테스트
├── test_operations.py       # ★ NEW — 이미지 처리 단위 테스트
├── test_auth_router.py      # ★ NEW — 인증 API 테스트
├── test_image_router.py     # ★ NEW — 이미지 API + 소유권 테스트
├── test_error_responses.py  # ★ NEW — 에러 응답 형식 검증
└── fixtures/                # (기존) 테스트용 이미지 파일
```

### conftest.py 핵심 패턴

```python
from sqlalchemy.pool import StaticPool

@pytest.fixture()
def session():
    # 테스트마다 새 in-memory SQLite DB 생성
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # 모든 커넥션이 같은 DB를 공유
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s

@pytest.fixture()
def client(session):
    # FastAPI 의존성을 테스트용 세션으로 오버라이드
    app.dependency_overrides[get_session] = lambda: (yield session)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

**StaticPool이 필요한 이유**: `sqlite://` (in-memory)는 기본적으로 커넥션마다 별도 DB를 생성한다. `StaticPool`은 단일 커넥션을 공유하게 하여, fixture에서 만든 테이블을 API 요청에서도 볼 수 있게 한다.

### 테스트 실행 결과

```
$ docker exec nogil-bench uv run pytest -v

tests/test_auth_router.py::TestRegister::test_register_success           PASSED
tests/test_auth_router.py::TestRegister::test_register_duplicate_email   PASSED
tests/test_auth_router.py::TestRegister::test_register_invalid_email     PASSED
tests/test_auth_router.py::TestLogin::test_login_success                 PASSED
tests/test_auth_router.py::TestLogin::test_login_wrong_password          PASSED
tests/test_auth_router.py::TestLogin::test_login_nonexistent_email       PASSED
tests/test_auth_router.py::TestMe::test_me_with_valid_token              PASSED
tests/test_auth_router.py::TestMe::test_me_without_token                 PASSED
tests/test_error_responses.py::test_error_has_error_code_and_message     PASSED
tests/test_error_responses.py::test_duplicate_email_error_format         PASSED
tests/test_error_responses.py::test_invalid_token_error_format           PASSED
tests/test_error_responses.py::test_invalid_operation_error_format       PASSED
tests/test_image_router.py::TestUpload::test_upload_image                PASSED
tests/test_image_router.py::TestListAndGet::test_list_images             PASSED
tests/test_image_router.py::TestListAndGet::test_get_image               PASSED
tests/test_image_router.py::TestProcess::test_process_image              PASSED
tests/test_image_router.py::TestProcess::test_download_not_processed     PASSED
tests/test_image_router.py::TestDelete::test_delete_image                PASSED
tests/test_image_router.py::TestAuthRequired::test_list_without_token    PASSED
tests/test_image_router.py::TestAuthRequired::test_upload_without_token  PASSED
tests/test_image_router.py::TestOwnership::test_access_other_user_image  PASSED
tests/test_image_router.py::TestOwnership::test_process_other_user_image PASSED
tests/test_image_router.py::TestOwnership::test_delete_other_user_image  PASSED
tests/test_image_router.py::TestOwnership::test_other_user_list_is_empty PASSED
tests/test_image_router.py::TestOwnership::test_image_not_found          PASSED
tests/test_operations.py::test_resize                                    PASSED
tests/test_operations.py::test_blur                                      PASSED
tests/test_operations.py::test_grayscale                                 PASSED
tests/test_security.py::test_hash_and_verify_password                    PASSED
tests/test_security.py::test_create_and_verify_token                     PASSED
tests/test_security.py::test_expired_token                               PASSED

==================== 31 passed in 11.03s ====================
Coverage: 93.64%
```

### 테스트 카테고리별 요약

| 카테고리 | 테스트 수 | 검증 내용 |
|----------|-----------|----------|
| Register | 3 | 성공 201, 중복 409, 잘못된 이메일 422 |
| Login | 3 | 성공 200, 잘못된 비밀번호 401, 없는 이메일 401 |
| Me | 2 | 유효한 토큰 200, 토큰 없음 401 |
| Image CRUD | 5 | upload, list, get, process, delete |
| Auth 필수 | 2 | 토큰 없이 목록 401, 토큰 없이 업로드 401 |
| 소유권 | 5 | 타인 조회/처리/삭제 403, 타인 목록 비어있음, 없는 이미지 404 |
| 에러 형식 | 4 | error_code+message 존재, 각 에러코드 형식 검증 |
| Security | 3 | bcrypt 해싱, JWT 생성/검증, 만료 토큰 |
| Operations | 3 | resize 크기, blur 반환 타입, grayscale 채널 |

### Shell 스크립트 → pytest 이전

기존 3개의 수동 테스트 스크립트를 pytest로 완전 이전하고 삭제했다:

```
삭제: src/scripts/test_auth_api.sh          → tests/test_auth_router.py
삭제: src/scripts/test_image_auth_api.sh    → tests/test_image_router.py
삭제: src/scripts/test_error_responses.sh   → tests/test_error_responses.py
```

---

## 3. 동시성 3가지 비교 벤치마크

### 생성된 파일

```
src/scripts/
├── bench_concurrency.py   # ★ NEW — sync vs threading vs multiprocessing
```

### 벤치마크 결과 (10개 태스크, 4 workers)

#### 순수 Python CPU-bound (GIL 영향 명확)

| 방식 | GIL=1 | GIL=0 |
|------|-------|-------|
| sync | 2.26s (1.00x) | 2.20s (1.00x) |
| **threading (4)** | **2.50s (1.10x) ← 오히려 느림!** | **0.71s (0.32x) ← 3배 빨라짐** |
| multiprocessing (4) | 0.71s (0.32x) | 0.69s (0.31x) |

#### Pillow blur (C 확장, GIL 릴리즈)

| 방식 | GIL=1 | GIL=0 |
|------|-------|-------|
| sync | 2.52s (1.00x) | 2.47s (1.00x) |
| threading (4) | 0.79s (0.31x) | 0.80s (0.32x) |
| multiprocessing (4) | 0.89s (0.35x) | 0.87s (0.35x) |

### 핵심 발견

1. **순수 Python CPU-bound + GIL=1**: threading이 오히려 10% 느림 (컨텍스트 스위칭 오버헤드만 추가)
2. **순수 Python CPU-bound + GIL=0**: threading이 3배 빠름 (free-threaded의 진짜 가치)
3. **Pillow (C 확장)**: GIL=1이든 GIL=0이든 threading이 둘 다 빠름 — C 확장이 내부에서 GIL을 릴리즈하기 때문
4. **multiprocessing**: GIL과 무관하게 항상 빠름, 단 프로세스 생성 오버헤드

### 교훈

```
GIL의 영향을 받는 것:   순수 Python 코드 (for 루프, 연산, 자료구조 조작)
GIL의 영향을 안 받는 것: C 확장 (Pillow, NumPy, scikit-learn 등)

→ free-threaded Python(GIL=0)의 가치는 순수 Python CPU-bound 작업에서 빛난다
→ C 확장 위주의 코드라면 기존에도 threading으로 병렬이 가능했음
```

---

## 4. Day 4 완료 체크리스트

- [x] 커스텀 예외 클래스 7개 (`core/exceptions.py`)
- [x] 전역 예외 핸들러 (`core/error_handlers.py`)
- [x] main.py에 핸들러 등록
- [x] 서비스 레이어 — built-in 예외 → 커스텀 예외로 교체
- [x] 라우터 — try-except 블록 전부 제거
- [x] dependencies.py — HTTPException → InvalidToken으로 교체
- [x] conftest.py + 공용 fixture (client, auth_headers, second_user_headers)
- [x] pytest 테스트 31개 작성 — 전부 PASS, 커버리지 94%
- [x] Shell 테스트 스크립트 3개 → pytest로 이전 후 삭제
- [x] 동시성 벤치마크 (`scripts/bench_concurrency.py`) — sync vs threading vs multiprocessing
- [x] GIL=1 vs GIL=0 비교 — 순수 Python vs C 확장 차이 확인

---

## 5. 현재 프로젝트 구조

```
src/
├── main.py                    # ★ MODIFIED — 전역 에러 핸들러 등록
├── core/
│   ├── config.py
│   ├── lifespan.py
│   ├── security.py
│   ├── dependencies.py        # ★ MODIFIED — InvalidToken 예외 사용
│   ├── middleware.py
│   ├── exceptions.py          # ★ NEW — 커스텀 예외 클래스 (7개)
│   └── error_handlers.py      # ★ NEW — 전역 예외 핸들러
├── model/
│   ├── database.py
│   ├── user.py
│   └── image.py
├── processor/
│   ├── operations.py
│   ├── sync_runner.py
│   └── async_runner.py
├── router/
│   ├── auth_router.py         # ★ MODIFIED — try-except 제거
│   └── image_router.py        # ★ MODIFIED — try-except 제거
├── service/
│   ├── auth_service.py        # ★ MODIFIED — 커스텀 예외 사용
│   └── image_service.py       # ★ MODIFIED — 커스텀 예외 사용
├── utility/
│   ├── logger.py
│   └── timer.py
└── scripts/
    ├── bench_gil.py
    ├── bench_baseline.py
    ├── bench_async.py
    ├── bench_concurrency.py   # ★ NEW — 동시성 3가지 비교
    └── test_operations.py

tests/
├── __init__.py                # ★ NEW
├── conftest.py                # ★ NEW — 공용 fixture
├── test_security.py           # ★ NEW — JWT/bcrypt 테스트 (3개)
├── test_operations.py         # ★ NEW — 이미지 처리 테스트 (3개)
├── test_auth_router.py        # ★ NEW — 인증 API 테스트 (8개)
├── test_image_router.py       # ★ NEW — 이미지 API 테스트 (13개)
├── test_error_responses.py    # ★ NEW — 에러 응답 형식 테스트 (4개)
└── fixtures/
    ├── test_cat.png
    ├── test_landscape.png
    ├── test_portrait.png
    ├── test_text.png
    └── output/
```

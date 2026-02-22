# Day 3 진행 기록

> 날짜: 2026-02-21~22 (금~토)
> 단계: JWT 인증 + 미들웨어 + asyncio 동시성 실험

---

## 1. JWT 인증 구현

### 생성된 파일

```
src/core/
├── security.py        # JWT 생성/검증, bcrypt 패스워드 해싱
├── dependencies.py    # get_current_user 의존성 (토큰 → User 객체)
├── middleware.py       # 요청 로깅 미들웨어
src/router/
├── auth_router.py     # 회원가입, 로그인, 내 정보 조회
src/service/
├── auth_service.py    # 인증 비즈니스 로직
```

### 인증 아키텍처 (4계층)

```
router/auth_router.py     HTTP 입출력 (상태코드, 스키마 변환)
        ↓
service/auth_service.py    비즈니스 로직 (중복 검사, 인증 판단)
        ↓
core/security.py           순수 유틸리티 (JWT 서명, bcrypt 해싱)
core/dependencies.py       요청마다 "지금 누구?" 판별
```

### 패스워드 해싱 (bcrypt)

```
평문 "mypassword123"
  ↓ hash_password()
"$2b$12$LJ3m4ys..." (60자 해시)
```

- `pwdlib[bcrypt]` 사용 — passlib의 후속 라이브러리 (Python 3.14+ 호환)
- bcrypt: 의도적으로 느린 해시(~100ms) → 브루트포스 공격에 비실용적
- 같은 평문도 매번 다른 해시 생성 (내부 salt)

### JWT 토큰 구조

```
eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0QGV4YW1wbGUuY29tIiwiZXhwIjoxNzA4NTAwMDAwfQ.서명
├─ Header ─────────────┤├─ Payload ──────────────────────────────────────────────┤├ Signature ┤
```

| 파트 | 내용 | 특징 |
|---|---|---|
| Header | `{"alg":"HS256","typ":"JWT"}` | 서명 알고리즘 |
| Payload | `{"sub":"test@example.com","exp":...}` | 누구나 디코딩 가능 → 민감정보 금지 |
| Signature | HMAC-SHA256(Header+Payload, SECRET_KEY) | 서버만 생성/검증 가능 |

- `sub`에 이메일을 넣음 — User 테이블에서 `email`이 unique index로 식별자 역할
- `exp`로 만료 시간 설정 (30분)

### 인증 API (3개 엔드포인트)

| 메서드 | 경로 | 동작 | 테스트 결과 |
|---|---|---|---|
| POST | `/auth/register` | 회원가입 | 201, 중복 시 409 |
| POST | `/auth/login` | 로그인 → JWT 반환 | 200, 실패 시 401 |
| GET | `/auth/me` | 현재 사용자 조회 (토큰 필수) | 200, 미인증 시 401 |

### 설계 결정

- `OAuth2PasswordRequestForm` 사용 — Swagger UI Authorize 버튼과 자동 연동, 필드명이 `username`인 것은 OAuth2 표준 스펙
- `OAuth2PasswordBearer(tokenUrl="/auth/login")` — 헤더에서 `Authorization: Bearer <token>` 자동 추출
- `EmailStr` (pydantic) — 이메일 형식 검증 자동화, `email-validator` 패키지 추가

---

## 2. 이미지 API에 인증 적용

### 변경 사항

**`service/image_service.py`**

- 모든 함수에 `user_id` 파라미터 추가
- `get_image_or_raise()` 신규 — 조회 + 소유권 검증을 한 곳에서 처리
  - 이미지 없음 → `LookupError` → router에서 404
  - 타인 이미지 → `PermissionError` → router에서 403
- `save_upload()` — `user_id`를 ImageRecord에 기록
- `list_images()` — `WHERE user_id = ?`로 본인 이미지만 필터링

**`router/image_router.py`**

- 모든 엔드포인트에 `Depends(get_current_user)` 추가
- `current_user.id`를 service 함수에 전달

### Depends() 체인 동작 방식

```python
def get_me(current_user: User = Depends(get_current_user)):
    ...

# FastAPI가 자동 실행하는 체인:
# 1. OAuth2PasswordBearer → 헤더에서 "Bearer xxx" 추출
# 2. get_session → DB 세션 생성
# 3. get_current_user → 토큰 검증 → DB에서 사용자 조회
# 4. → User 객체를 current_user에 주입
```

### 소유권 검증 테스트 결과

| 시나리오 | 기대 | 결과 |
|---|---|---|
| 토큰 없이 목록 조회 | 401 | PASS |
| 토큰 없이 업로드 | 401 | PASS |
| Alice 본인 이미지 조회 | 200 | PASS |
| Alice 목록 조회 | 200 | PASS |
| Bob이 Alice 이미지 조회 | 403 | PASS |
| Bob이 Alice 이미지 처리 | 403 | PASS |
| Bob이 Alice 이미지 삭제 | 403 | PASS |
| Bob 목록에 Alice 이미지 없음 | 0건 | PASS |
| Alice 본인 이미지 삭제 | 200 | PASS |
| Alice 이미지 업로드 | 200 | PASS |

---

## 3. 요청 로깅 미들웨어

### 구현 (`core/middleware.py`)

```python
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (perf_counter() - start) * 1000
        # 500ms 초과 → WARNING (slow), 이하 → INFO
```

### 기록 항목

| 항목 | 예시 |
|---|---|
| 메서드 | `GET`, `POST`, `DELETE` |
| 경로 | `/api/images/1/process` |
| 클라이언트 IP | `172.18.0.1` |
| 상태코드 | `200`, `401`, `403` |
| 처리시간 | `3ms`, `523ms (slow)` |

### 로그 출력 예시

```
2026-02-22 00:21:49 | INFO     | GET /health | 172.18.0.1 | 200 | 2ms
2026-02-22 00:21:49 | INFO     | POST /auth/login | 172.18.0.1 | 200 | 242ms
2026-02-22 00:21:49 | INFO     | GET /api/images/ | 172.18.0.1 | 200 | 6ms
2026-02-22 00:21:49 | INFO     | GET /api/images/ | 172.18.0.1 | 401 | 0ms
```

- uvicorn 기본 액세스 로그와 중복되어 `access_log=False`로 비활성화
- 모든 엔드포인트에 자동 적용 (라우터 코드 수정 불필요)

---

## 4. asyncio 동시성 실험

### 생성된 파일

```
src/processor/
├── async_runner.py         # asyncio 러너 (pure async + run_in_executor)
src/scripts/
├── bench_async.py          # async vs sync 벤치마크
```

### async_runner 두 가지 모드

| 모드 | 설명 |
|---|---|
| `run()` | 순수 async — CPU-bound 함수를 async로 감싸기만 함 |
| `run_with_executor()` | `run_in_executor`로 스레드풀에 CPU 작업 위임 |

### 벤치마크 결과 (10장 blur, GIL=0)

| 방식 | 시간 | 배율 | 분석 |
|---|---|---|---|
| **sync** | 2.486s | 1.00x | 기준선 |
| **async (pure)** | 2.276s | 0.92x | sync와 거의 동일 |
| **executor (1 worker)** | 2.375s | 0.96x | 스레드 1개 = 순차와 같음 |
| **executor (2 workers)** | 1.263s | 0.51x | 2배 빨라짐 |
| **executor (4 workers)** | 0.763s | 0.31x | 3.3배 빨라짐 |

### 핵심 결론

- **async (pure)가 sync와 같은 이유**: asyncio는 `await` 지점에서 다른 작업으로 전환하는 협력적 멀티태스킹. 이미지 처리는 CPU를 계속 점유하므로 양보할 시점이 없어 순차 실행과 동일
- **run_in_executor가 빠른 이유**: CPU 작업을 스레드풀에 던지고 `await gather()`로 동시에 대기. GIL=0이라 스레드들이 진짜 병렬로 실행
- **GIL=1이었다면**: executor도 sync와 비슷했을 것 (GIL이 스레드 병렬 실행을 막으므로)

---

## 5. Day 3 완료 체크리스트

- [x] JWT 생성/검증 + bcrypt 해싱 (`core/security.py`)
- [x] `get_current_user` 의존성 주입 (`core/dependencies.py`)
- [x] 인증 API — register, login, me (`router/auth_router.py` + `service/auth_service.py`)
- [x] 이미지 API에 인증 적용 — 소유권 검증, 403 Forbidden
- [x] 요청 로깅 미들웨어 (`core/middleware.py`) — 메서드, 경로, IP, 상태코드, 처리시간
- [x] asyncio 러너 (`processor/async_runner.py`) — pure async + run_in_executor
- [x] async vs sync 벤치마크 — CPU-bound에서 asyncio 한계 확인
- [x] 테스트 스크립트 (`scripts/test_auth_api.sh`, `scripts/test_image_auth_api.sh`)
- [x] 추가 의존성: `email-validator>=2.0.0`

---

## 6. 현재 프로젝트 구조

```
src/
├── main.py
├── core/
│   ├── config.py          # + JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_MINUTES
│   ├── lifespan.py
│   ├── security.py        # ★ NEW — JWT + bcrypt
│   ├── dependencies.py    # ★ NEW — get_current_user
│   └── middleware.py       # ★ NEW — 요청 로깅
├── model/
│   ├── database.py
│   ├── user.py
│   └── image.py
├── processor/
│   ├── operations.py
│   ├── sync_runner.py
│   └── async_runner.py    # ★ NEW — asyncio 러너
├── router/
│   ├── auth_router.py     # ★ NEW — 인증 API
│   └── image_router.py    # ★ MODIFIED — Depends(get_current_user) 적용
├── service/
│   ├── auth_service.py    # ★ NEW — 인증 로직
│   └── image_service.py   # ★ MODIFIED — user_id 소유권 검증
├── utility/
│   ├── logger.py
│   └── timer.py
└── scripts/
    ├── bench_gil.py
    ├── bench_baseline.py
    ├── bench_async.py      # ★ NEW — async 벤치마크
    ├── test_operations.py
    ├── test_auth_api.sh    # ★ NEW — 인증 API 테스트
    └── test_image_auth_api.sh  # ★ NEW — 이미지+인증 통합 테스트
```

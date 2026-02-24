# Nogil-bench

> Free-threaded Python(3.14t, GIL=0)으로 이미지 프로세싱 백엔드를 구축하고,
> 4가지 동시성 모델의 성능을 비교하는 실습 프로젝트

## API 문서

**온라인 API 문서 (Swagger UI):**

https://ksm463.github.io/Nogil-bench/

**로컬에서 확인:**

| URL | 설명 |
|-----|------|
| http://localhost:8001/docs | Swagger UI (대화형) |
| http://localhost:8001/redoc | ReDoc (읽기 전용) |
| http://localhost:8001/openapi.json | OpenAPI 3.1 JSON 스펙 |

```bash
# Swagger 정적 문서 재생성
docker exec nogil-bench-compose uv run python src/scripts/export_openapi.py
```

---

## 프로젝트 개요

Python의 GIL(Global Interpreter Lock)은 멀티스레드에서 CPU-bound 작업의 병렬 실행을 막는 근본적인 제약이었다. Python 3.14에서 공식 지원(PEP 779)된 free-threaded 모드는 GIL을 비활성화하여 진정한 멀티스레드 병렬 처리를 가능하게 한다.

이 프로젝트는 **이미지 프로세싱 REST API**를 구축하면서:

1. FastAPI 기반 백엔드 패턴(인증, CRUD, 에러 처리, 테스트)을 구현하고
2. 동일한 CPU-bound 작업을 **4가지 동시성 모델**로 실행하여 성능을 비교한다

### 4가지 동시성 모델

```
1. sync              — 순차 처리 (기준선)
2. threading (GIL=1) — GIL로 인해 실제로는 순차 실행
3. multiprocessing   — 진짜 병렬이지만 프로세스 생성/IPC 오버헤드
4. free-threaded     — GIL=0 + threading = 진정한 멀티스레드 병렬
```

---

## 기술 스택

| 항목 | 선택 |
|------|------|
| 언어 | Python 3.14t (free-threaded, `PYTHON_GIL=0`) |
| 웹 프레임워크 | FastAPI + Uvicorn |
| DB | SQLite (개발) / PostgreSQL (동시성 실험) |
| ORM | SQLModel (SQLAlchemy + Pydantic) |
| 인증 | JWT (PyJWT + pwdlib/bcrypt) |
| 이미지 처리 | Pillow |
| 패키지 관리 | uv |
| 테스트 | pytest (86개, 커버리지 93%) |
| 린팅 | Ruff |
| 컨테이너 | Docker + Docker Compose |

---

## 빠른 시작

### 사전 요구사항

- Docker + Docker Compose

### 실행

```bash
# 전체 스택 시작 (앱 + PostgreSQL)
docker compose up -d

# 로그 확인
docker compose logs -f app

# API 접속
curl http://localhost:8001/health
```

### 테스트

```bash
# 의존성 동기화 (최초 1회)
docker exec nogil-bench-compose uv sync --extra test --extra dev

# 전체 테스트 실행
docker exec -w /app nogil-bench-compose uv run pytest

# Ruff 린팅
docker exec -w /app nogil-bench-compose uv run ruff check src/ tests/
```

### 종료

```bash
docker compose down
```

---

## 프로젝트 구조

```
src/
├── main.py                  # FastAPI 앱 생성, 라우터 등록
├── core/
│   ├── config.py            # pydantic-settings 환경변수 관리
│   ├── lifespan.py          # startup/shutdown 생명주기
│   ├── security.py          # JWT 생성/검증, bcrypt 해싱
│   ├── dependencies.py      # Depends() 의존성 (get_current_user)
│   ├── middleware.py         # 요청 로깅 미들웨어
│   ├── exceptions.py        # 커스텀 예외 클래스
│   ├── error_handlers.py    # 전역 예외 핸들러
│   └── openapi.py           # 커스텀 OpenAPI 스키마
├── router/                  # HTTP 엔드포인트
│   ├── auth_router.py       # 회원가입, 로그인, 토큰
│   ├── image_router.py      # 이미지 CRUD + 처리
│   ├── benchmark_router.py  # 벤치마크 실행/비교
│   └── job_router.py        # 배치 작업 관리
├── service/                 # 비즈니스 로직
├── model/                   # DB 모델 (SQLModel)
├── processor/               # 이미지 처리 + 동시성 실행기
│   ├── operations.py        # CPU-bound 이미지 처리 함수
│   ├── sync_runner.py       # 동기 순차 처리
│   ├── thread_runner.py     # threading (GIL 영향)
│   ├── mp_runner.py         # multiprocessing
│   └── frethread_runner.py  # free-threaded (GIL=0)
├── utility/                 # 로깅, 타이머
└── scripts/                 # 벤치마크 스크립트

tests/                       # pytest 테스트 (80개)
swagger/                     # 정적 API 문서 (GitHub Pages)
docs/                        # Day별 진행 기록
```

---

## API 엔드포인트

### System

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/health` | 서버 상태, Python 버전, GIL 여부 |

### Auth

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/auth/register` | 회원가입 (이메일 + 패스워드) |
| POST | `/auth/login` | 로그인 → JWT 토큰 반환 |
| GET | `/auth/me` | 현재 사용자 정보 조회 |

### Images

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/images/upload` | 이미지 업로드 |
| GET | `/api/images/` | 내 이미지 목록 |
| GET | `/api/images/{id}` | 이미지 상세 조회 |
| POST | `/api/images/{id}/process` | 이미지 처리 (blur, resize 등) |
| GET | `/api/images/{id}/download` | 처리된 이미지 다운로드 |
| DELETE | `/api/images/{id}` | 이미지 삭제 |

### Benchmarks

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/benchmarks/run` | 벤치마크 실행 |
| GET | `/api/benchmarks/` | 결과 목록 |
| GET | `/api/benchmarks/{id}` | 결과 상세 |
| GET | `/api/benchmarks/compare` | 여러 결과 비교 |

### Jobs (배치 처리)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/jobs/batch` | 배치 작업 생성 (202 Accepted) |
| GET | `/api/jobs/` | 내 작업 목록 |
| GET | `/api/jobs/{id}` | 작업 상태 조회 |
| GET | `/api/jobs/{id}/result` | 완료된 작업 결과 |

---

## 벤치마크 결과

### 이미지 처리 동시성 비교 (100장, blur, GIL=0)

| 방식 | w=1 | w=2 | w=4 | w=8 |
|------|-----|-----|-----|-----|
| sync | 22.1s (기준) | — | — | — |
| threading | 24.0s | 11.5s | 6.6s | **4.1s** |
| multiprocessing | 31.4s | 18.9s | 13.3s | 11.7s |
| frethread | 22.0s | 11.5s | 6.5s | **4.2s** |

- threading과 frethread가 거의 동일 (Pillow C 확장이 GIL을 자동 해제)
- 워커 8개에서 sync 대비 **5배** 속도
- multiprocessing이 가장 느림 (프로세스 생성 + pickle 오버헤드)

### SQLite vs PostgreSQL 동시 쓰기 (GIL=0)

| 스레드 | SQLite writes/s | PostgreSQL writes/s | PG/SQLite |
|--------|-----------------|---------------------|-----------|
| 1 | 260 | 487 | 1.9x |
| 4 | 226 | 1,543 | **6.8x** |
| 8 | 362 | 2,945 | **8.1x** |
| 16 | 425 | 4,794 | **11.3x** |

- SQLite: 스레드를 늘려도 writes/s 정체 (파일 레벨 잠금)
- PostgreSQL: MVCC 덕분에 스레드에 비례하여 증가

### Thread-Safety 실험 (GIL=0, 8스레드)

| 실험 | Lock 없음 | Lock 사용 |
|------|----------|----------|
| 공유 카운터 (80만 증가) | ~15만 (**81% 손실**) | 80만 (정확) |
| Check-then-act (limit=10만) | limit 초과 | limit 정확 준수 |

- GIL=1에서는 "우연히 안전"했던 코드가 GIL=0에서 즉시 깨짐
- `threading.Lock`으로 critical section을 보호하면 해결

---

## 학습 기록

| Day | 주제 | 핵심 |
|-----|------|------|
| [Day 1](docs/day1-progress.md) | 프로젝트 셋업 | Docker + CPython 소스 빌드, GIL=0 vs 1 벤치마크 |
| [Day 2](docs/day2-progress.md) | 이미지 CRUD | SQLModel, 서비스 레이어 패턴, 기준선 측정 |
| [Day 3](docs/day3-progress.md) | JWT 인증 | bcrypt, OAuth2, 미들웨어, asyncio 실험 |
| [Day 4](docs/day4-progress.md) | 테스트 + 에러 처리 | pytest 31개, 커스텀 예외, 동시성 3종 비교 |
| [Day 5](docs/day5-progress.md) | Free-threaded 실험 | 4가지 러너, 배치 API, 벤치마크 매트릭스 |
| [Day 6](docs/day6-progress.md) | DB 동시성 | SQLite 한계, PostgreSQL MVCC, 커넥션 풀 |
| [Day 7](docs/day7-progress.md) | 통합 + 마무리 | API 문서, 코드 리뷰, README, 최종 리포트, thread-safety |

---

## 참고 자료

- [PEP 703 – Making the Global Interpreter Lock Optional](https://peps.python.org/pep-0703/)
- [PEP 779 – Free-threaded CPython officially supported in 3.14](https://peps.python.org/pep-0779/)
- [Python free-threading guide](https://docs.python.org/3.14/howto/free-threading-python.html)
- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)
- [SQLModel 공식 문서](https://sqlmodel.tiangolo.com/)

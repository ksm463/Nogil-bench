# nogil-bench: Free-threaded Python Backend Practice Project

> Python 3.14t의 free-threaded(no-GIL) 모드를 활용한 이미지 프로세싱 백엔드 실습 프로젝트
>
> 기간: 1주일 (7일)
> 목표: 백엔드 기초 패턴 습득 + Python 동시성 모델 4가지 비교 실험

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [기술 스택](#2-기술-스택)
3. [프로젝트 구조](#3-프로젝트-구조)
4. [Day별 커리큘럼](#4-day별-커리큘럼)
5. [핵심 벤치마크 설계](#5-핵심-벤치마크-설계)
6. [학습 방법](#6-학습-방법)
7. [참고 자료](#7-참고-자료)

---

## 1. 프로젝트 개요

### 배경

Python의 GIL(Global Interpreter Lock)은 멀티스레드에서 CPU-bound 작업의 병렬 실행을 막는 근본적인 제약이었다. Python 3.13에서 실험적으로 도입되고 3.14에서 공식 지원(PEP 779)된 free-threaded 모드(PEP 703)는 GIL을 비활성화하여 진정한 멀티스레드 병렬 처리를 가능하게 한다.

이 프로젝트는 **이미지 프로세싱 API**를 구축하면서:

1. FastAPI 기반 백엔드 패턴을 처음부터 직접 구현하고
2. 동일한 CPU-bound 작업을 4가지 동시성 모델로 실행하여 성능을 비교한다

### 무엇을 만드는가

GPU/AI 없이 **CPU만으로 이미지 변환**(리사이즈, 블러, 샤프닝, 워터마크, 포맷 변환)을 처리하는 REST API 서버를 만든다.

핵심 기능:

- 이미지 업로드, 처리, 다운로드
- 배치 처리 (여러 이미지를 한 번에)
- 4가지 동시성 방식으로 동일 작업 실행 및 성능 비교
- 벤치마크 결과 저장 및 조회

### 왜 이미지 프로세싱인가

| 이유 | 설명 |
|------|------|
| GIL 병목 체감 | 이미지 처리는 CPU-bound → GIL 유무에 따른 성능 차이가 명확 |
| 업무 연관 | 기존 비전 AI 파이프라인과 개념이 연결됨 (PIL/OpenCV) |
| GPU 불필요 | Pillow만으로 충분, Docker에서 바로 실행 |
| 측정 용이 | 처리 시간, CPU 사용률, 메모리 등 정량적 비교 가능 |

---

## 2. 기술 스택

### 확정 사항

| 항목 | 선택 | 이유 |
|------|------|------|
| **언어** | Python 3.14t | free-threaded 빌드 (GIL 비활성화 가능) |
| **웹 프레임워크** | FastAPI + Uvicorn | 기존 grpc-diffusion-server web-manager와 동일 패턴 |
| **DB** | SQLite → PostgreSQL | Day 1-4는 SQLite로 빠르게 시작, Day 6에서 PostgreSQL로 마이그레이션 |
| **ORM** | SQLModel | SQLAlchemy + Pydantic 통합, FastAPI 제작자가 설계 |
| **인증** | 직접 JWT 구현 | python-jose + passlib로 토큰 생성/검증, 패스워드 해싱 직접 구현 |
| **이미지 처리** | Pillow | CPU-bound 이미지 변환 (리사이즈, 필터, 워터마크 등) |
| **패키지 관리** | uv | pip 대비 10배 빠른 설치, lockfile 지원 |
| **테스트** | pytest | pytest-asyncio, pytest-cov 포함 |
| **린팅** | Ruff | 빠르고 설정이 간단한 Python linter/formatter |
| **로깅** | Loguru | 설정 없이 바로 사용 가능한 구조화된 로깅 |
| **컨테이너** | Docker + Docker Compose | 개발 환경 격리, PostgreSQL 포함 |

### 환경 구성

```
Docker Container (개발 환경)
├── Python 3.14t (free-threaded 빌드)
├── PYTHON_GIL=0 환경변수로 GIL 비활성화
├── uv (패키지 관리)
├── SQLite (Day 1-4) → PostgreSQL 컨테이너 추가 (Day 6)
└── 볼륨 마운트: 로컬 코드 편집 → 컨테이너에서 실행
```

### 이 프로젝트에서 배우는 grpc-diffusion-server 패턴

| grpc-diffusion-server 패턴 | nogil-bench에서 배우는 방식 |
|---------------------------|--------------------------|
| FastAPI + Jinja2 | FastAPI (API 중심, 템플릿은 선택) |
| Supabase 인증 위임 | JWT 직접 구현 (원리 이해) |
| Pydantic 스키마 | SQLModel + Pydantic v2 |
| 서비스 레이어 분리 (router → service) | 동일 패턴 적용 |
| `app.state` + `Depends()` DI | 동일 패턴 적용 |
| `lifespan` context manager | 동일 패턴 적용 |
| Docker 멀티스테이지 빌드 | 동일 패턴 적용 |
| pytest + mock | 동일 패턴 적용 |
| gRPC + Redis 비동기 큐 | BackgroundTasks + 작업 큐 (간소화) |
| Prometheus 메트릭 | 벤치마크 결과 API로 대체 |

---

## 3. 프로젝트 구조

### 최종 완성 형태

```
nogil-bench/
├── Dockerfile                      # free-threaded Python 기반 개발 환경
├── docker-compose.yml              # app + PostgreSQL
├── pyproject.toml                  # uv 의존성 관리
├── .env.example                    # 환경변수 템플릿
├── README.md
│
├── src/
│   ├── main.py                     # FastAPI 앱 생성, 라우터 등록
│   │
│   ├── core/                       # 앱 핵심 설정
│   │   ├── config.py               # 설정 관리 (pydantic-settings)
│   │   ├── lifespan.py             # startup/shutdown 생명주기
│   │   ├── security.py             # JWT 생성/검증, bcrypt 패스워드 해싱
│   │   └── dependencies.py         # Depends() 의존성 팩토리
│   │
│   ├── router/                     # HTTP 엔드포인트 (요청/응답만 담당)
│   │   ├── auth_router.py          # 회원가입, 로그인, 토큰 갱신
│   │   ├── image_router.py         # 이미지 업로드, 단건 처리, 다운로드
│   │   ├── job_router.py           # 배치 작업 생성, 상태 조회, 결과
│   │   └── benchmark_router.py     # 벤치마크 실행, 결과 조회/비교
│   │
│   ├── service/                    # 비즈니스 로직 (라우터와 분리)
│   │   ├── auth_service.py         # 인증 로직
│   │   ├── image_service.py        # 이미지 처리 오케스트레이션
│   │   ├── job_service.py          # 배치 작업 관리
│   │   └── benchmark_service.py    # 벤치마크 실행 및 결과 비교
│   │
│   ├── model/                      # DB 모델 + API 스키마 (SQLModel)
│   │   ├── database.py             # 엔진, 세션, 테이블 생성
│   │   ├── user.py                 # User 모델
│   │   ├── image.py                # ImageRecord 모델
│   │   ├── job.py                  # Job 모델 (배치 작업)
│   │   └── benchmark.py            # BenchmarkResult 모델
│   │
│   ├── processor/                  # 이미지 처리 + 동시성 실행기
│   │   ├── operations.py           # 순수 CPU-bound 이미지 처리 함수
│   │   │                           #   resize, blur, sharpen, watermark,
│   │   │                           #   grayscale, rotate, format_convert
│   │   ├── sync_runner.py          # 동기 순차 처리 (기준선)
│   │   ├── async_runner.py         # asyncio 기반 처리
│   │   ├── thread_runner.py        # threading 기반 (GIL 영향 확인)
│   │   ├── mp_runner.py            # multiprocessing 기반
│   │   └── frethread_runner.py     # free-threaded (GIL=0) 처리
│   │
│   └── utility/
│       ├── logger.py               # Loguru 설정
│       └── timer.py                # 성능 측정 데코레이터/컨텍스트 매니저
│
├── tests/
│   ├── conftest.py                 # 공용 fixture (TestClient, 테스트 DB, mock)
│   ├── unit/
│   │   ├── test_auth_router.py
│   │   ├── test_auth_service.py
│   │   ├── test_image_router.py
│   │   ├── test_image_service.py
│   │   ├── test_operations.py      # 이미지 처리 함수 단위 테스트
│   │   ├── test_benchmark.py
│   │   └── test_security.py        # JWT, 패스워드 해싱 테스트
│   └── integration/
│       └── test_e2e_flow.py        # 회원가입→로그인→업로드→처리→다운로드
│
├── uploads/                        # 업로드된 원본 이미지
├── outputs/                        # 처리된 결과 이미지
└── benchmarks/                     # 벤치마크 결과 저장
```

### 핵심 레이어 설계

```
┌─────────────────────────────────────┐
│           router/ (HTTP)            │  요청/응답, 유효성 검증
├─────────────────────────────────────┤
│           service/ (로직)            │  비즈니스 로직, 오케스트레이션
├─────────────────────────────────────┤
│     model/ (DB)    processor/ (CPU) │  데이터 영속성 / 이미지 처리
└─────────────────────────────────────┘
```

---

## 4. Day별 커리큘럼

### Day 1 (월) — 프로젝트 셋업 + FastAPI 기초

#### 백엔드 학습

- [ ] Docker 컨테이너 구성 (free-threaded Python 베이스 이미지)
- [ ] `uv init` + `pyproject.toml` 의존성 설정
- [ ] FastAPI 앱 뼈대 작성
  - `main.py` — 앱 생성, 라우터 등록
  - `core/config.py` — pydantic-settings로 환경변수 관리
  - `core/lifespan.py` — startup/shutdown 생명주기
- [ ] 헬스체크 엔드포인트 (`GET /health`)
- [ ] Loguru 로깅 설정 (`utility/logger.py`)

#### 동시성 학습

- [ ] GIL 개념 이해: GIL이 뭔지, 왜 CPU-bound에서 병목인지
- [ ] `PYTHON_GIL=0` 환경변수 설정 확인
- [ ] 간단한 실험 스크립트 작성:
  ```python
  # CPU-bound 작업 (피보나치 등)을 threading vs sequential로 실행
  # GIL=1 vs GIL=0 에서 시간 차이 측정
  ```

#### 결과물

- 컨테이너에서 FastAPI 서버 실행
- `http://localhost:8000/health` 응답 확인
- `http://localhost:8000/docs` Swagger UI 접속 확인
- GIL=1 vs GIL=0 간단한 벤치마크 결과

---

### Day 2 (화) — 이미지 CRUD + 파일 업로드

#### 백엔드 학습

- [ ] SQLModel DB 모델 정의
  - `model/database.py` — 엔진, 세션, 테이블 자동 생성
  - `model/user.py` — User 테이블 (Day 3 인증을 위해 미리 생성)
  - `model/image.py` — ImageRecord 테이블
- [ ] 이미지 처리 함수 작성 (`processor/operations.py`)
  - `resize(image, width, height)`
  - `blur(image, radius)`
  - `sharpen(image)`
  - `watermark(image, text)`
  - `grayscale(image)`
  - `rotate(image, degrees)`
- [ ] REST API 구현 (`router/image_router.py` + `service/image_service.py`)
  ```
  POST /api/images/upload           # 이미지 업로드 (UploadFile)
  GET  /api/images/                  # 목록 조회
  GET  /api/images/{id}              # 상세 조회
  POST /api/images/{id}/process      # 처리 요청 (operation + params)
  GET  /api/images/{id}/download     # 처리된 이미지 다운로드
  DELETE /api/images/{id}            # 삭제
  ```
- [ ] 서비스 레이어 패턴 적용: 라우터는 HTTP만 담당, 로직은 서비스에

#### 동시성 학습

- [ ] `processor/sync_runner.py` 작성 — 10장 이미지 순차 처리
- [ ] 처리 시간 측정 유틸리티 (`utility/timer.py`)
- [ ] 기준선(baseline) 성능 기록

#### 결과물

- 이미지 업로드 → 처리 (리사이즈 등) → 다운로드 전체 플로우 동작
- 10장 이미지 순차 처리 시간 측정 완료

---

### Day 3 (수) — 인증 (JWT) + 미들웨어

#### 백엔드 학습

- [ ] JWT 인증 직접 구현 (`core/security.py`)
  - `create_access_token(data, expires_delta)` — JWT 생성
  - `verify_token(token)` — JWT 검증 및 payload 추출
  - `hash_password(password)` — bcrypt 해싱
  - `verify_password(plain, hashed)` — 패스워드 검증
- [ ] 인증 API (`router/auth_router.py` + `service/auth_service.py`)
  ```
  POST /auth/register              # 회원가입 (이메일, 패스워드)
  POST /auth/login                 # 로그인 → JWT 토큰 반환
  POST /auth/refresh               # 토큰 갱신
  GET  /auth/me                    # 현재 사용자 정보
  ```
- [ ] 의존성 주입으로 인증 적용 (`core/dependencies.py`)
  - `get_current_user` — JWT에서 사용자 추출
  - 이미지 API에 인증 적용 (본인 이미지만 접근)
- [ ] 요청 로깅 미들웨어
  - 메서드, 경로, 클라이언트 IP, 응답 상태 코드, 처리 시간(ms)
  - 느린 요청 (>500ms) 경고 로그

#### 동시성 학습

- [ ] `processor/async_runner.py` 작성
  - asyncio로 파일 I/O (읽기/쓰기) 비동기 처리
  - CPU-bound 이미지 처리에서 asyncio가 왜 도움이 안 되는지 실험
  - `run_in_executor`로 스레드풀 위임 패턴 경험

#### 결과물

- 회원가입 → 로그인 → JWT 발급 → 인증된 요청으로 이미지 처리 전체 플로우
- asyncio vs sync 성능 비교 (CPU-bound에서 차이 없음 확인)

---

### Day 4 (목) — 테스트 + 에러 처리

#### 백엔드 학습

- [ ] 테스트 인프라 구축
  - `tests/conftest.py` — TestClient, 테스트용 SQLite DB, fixture
  - 인증 관련 fixture (테스트용 사용자, JWT 토큰)
- [ ] 인증 API 테스트 (`tests/unit/test_auth_router.py`)
  - 회원가입 성공/실패 (중복 이메일)
  - 로그인 성공/실패 (잘못된 비밀번호)
  - 인증 없이 보호된 엔드포인트 접근 시 401
- [ ] 이미지 API 테스트 (`tests/unit/test_image_router.py`)
  - 업로드, 처리, 다운로드
  - 다른 사용자 이미지 접근 시 403
  - 존재하지 않는 이미지 404
- [ ] 이미지 처리 함수 단위 테스트 (`tests/unit/test_operations.py`)
- [ ] 구조화된 에러 처리
  - 커스텀 예외 클래스 (NotFound, Forbidden, BadRequest)
  - 전역 exception handler → 일관된 JSON 에러 응답
- [ ] Ruff 린팅 설정 (`pyproject.toml`)

#### 동시성 학습

- [ ] `processor/thread_runner.py` 작성 — `threading` + GIL 있는 상태
- [ ] `processor/mp_runner.py` 작성 — `multiprocessing`
- [ ] 3가지 비교 실험 (10장 이미지 기준):
  ```
  sync           → 기준선
  threading GIL=1 → GIL 병목 확인 (sync와 비슷하거나 더 느림)
  multiprocessing → 프로세스 생성 오버헤드 vs 병렬 이득
  ```

#### 결과물

- 테스트 전부 통과 (`uv run pytest`)
- 3가지 동시성 방식 성능 비교 데이터 확보
- 일관된 에러 응답 형식 동작

---

### Day 5 (금) — Free-threaded 실험 + 배치 API ⭐ 핵심 Day

#### 백엔드 학습

- [ ] 배치 처리 API 설계
  ```
  POST /api/jobs/batch              # 여러 이미지 배치 처리 요청
                                    # → 202 Accepted + job_id 즉시 반환
  GET  /api/jobs/                   # 내 작업 목록
  GET  /api/jobs/{job_id}           # 작업 상태 (queued/processing/completed/failed)
  GET  /api/jobs/{job_id}/result    # 완료된 결과 다운로드
  ```
- [ ] Job 모델 (`model/job.py`) — 상태 관리, 진행률, 소요 시간
- [ ] `BackgroundTasks` 또는 별도 스레드에서 비동기 처리
- [ ] 작업 상태 업데이트 (DB에 진행률 저장)

#### 동시성 학습 (이 프로젝트의 핵심)

- [ ] `processor/frethread_runner.py` 작성 — `PYTHON_GIL=0` + `threading`
- [ ] **4가지 동시성 방식 벤치마크 실행**:
  ```
  1. sync              — 순차 처리 (기준선)
  2. threading (GIL=1)  — GIL 병목 확인
  3. multiprocessing    — 프로세스 오버헤드 확인
  4. threading (GIL=0)  — free-threaded 진정한 병렬 처리
  ```
- [ ] 스레드/프로세스 수(1, 2, 4, 8)별 스케일링 측정
- [ ] 벤치마크 API (`router/benchmark_router.py`)
  ```
  POST /api/benchmarks/run          # 벤치마크 실행 (이미지 수, 스레드 수, 방식)
  GET  /api/benchmarks/             # 과거 결과 목록
  GET  /api/benchmarks/{id}         # 결과 상세
  GET  /api/benchmarks/compare      # 여러 결과 비교
  ```
- [ ] 벤치마크 결과 모델 (`model/benchmark.py`) — DB에 결과 저장

#### 결과물

- 배치 처리 API 동작 (비동기 작업 생성 → 상태 조회 → 결과 다운로드)
- 4가지 동시성 방식 벤치마크 결과
- 벤치마크 결과 API를 통해 조회/비교 가능

---

### Day 6 (토) — Docker 정리 + PostgreSQL 마이그레이션

#### 백엔드 학습

- [ ] `docker-compose.yml`에 PostgreSQL 컨테이너 추가
  ```yaml
  services:
    app:
      build: .
      environment:
        - PYTHON_GIL=0
        - DATABASE_URL=postgresql://...
      volumes:
        - ./src:/app/src        # 코드 마운트
      depends_on:
        - db
    db:
      image: postgres:16
      environment:
        - POSTGRES_DB=nogil_bench
        - POSTGRES_USER=...
        - POSTGRES_PASSWORD=...
      volumes:
        - pgdata:/var/lib/postgresql/data
  ```
- [ ] SQLite → PostgreSQL 마이그레이션
  - SQLModel 엔진 URL만 변경하면 동작하는지 확인
  - 차이점이 있다면 해결
- [ ] Dockerfile 멀티스테이지 빌드
  ```dockerfile
  # Stage 1: base — 의존성 설치
  # Stage 2: test — 테스트 실행 (CI용)
  # Stage 3: production — 최종 이미지 (테스트 제외)
  ```
- [ ] `.env.example` + `.env.development` + `.env.production` 환경 분리
- [ ] 각 서비스에 healthcheck 추가
- [ ] MCP PostgreSQL Server 설정 (개발 도구)
  - Claude Code에서 DB 스키마 확인, 데이터 조회 등 개발 편의 용도

#### 동시성 학습

- [ ] 벤치마크 결과를 PostgreSQL에 저장
- [ ] 대규모 벤치마크 매트릭스 실행:
  ```
  이미지 수: 10, 50, 100장
  스레드 수: 1, 2, 4, 8
  방식: sync, threading(GIL), multiprocessing, free-threaded
  = 총 48가지 조합
  ```
- [ ] 결과 비교 API로 매트릭스 조회

#### 결과물

- `docker compose up`으로 전체 스택 (app + PostgreSQL) 실행
- PostgreSQL에서 모든 기능 정상 동작
- 48가지 조합 벤치마크 매트릭스 데이터

---

### Day 7 (일) — 통합 + 최종 벤치마크 리포트

#### 백엔드 학습

- [ ] API 문서 정리
  - 모든 엔드포인트에 summary, description 추가
  - 에러 응답 명세 (401, 403, 404, 422)
  - OpenAPI/Swagger에서 깔끔하게 보이는지 확인
- [ ] E2E 통합 테스트 (`tests/integration/test_e2e_flow.py`)
  ```
  회원가입 → 로그인 → 이미지 업로드 → 단건 처리 → 다운로드
  → 배치 처리 → 상태 조회 → 결과 다운로드
  → 벤치마크 실행 → 결과 비교
  ```
- [ ] 코드 자가 리뷰 체크리스트:
  ```
  □ 모든 엔드포인트에 인증 적용 확인
  □ 입력 유효성 검증 (Pydantic/SQLModel)
  □ 에러 응답 일관성
  □ 로그에 민감 정보(패스워드, 토큰) 노출 없음
  □ 테스트 커버리지 80%+ (신규 코드 기준)
  □ Ruff 린팅 통과
  ```
- [ ] README.md 작성

#### 동시성 학습

- [ ] 최종 벤치마크 리포트 정리:
  ```
  | 방식              | 10장   | 50장    | 100장   | 메모리  | CPU% |
  |-------------------|--------|---------|---------|---------|------|
  | sync              | ???ms  | ???ms   | ???ms   | ???MB   | ???% |
  | threading (GIL=1) | ???ms  | ???ms   | ???ms   | ???MB   | ???% |
  | multiprocessing   | ???ms  | ???ms   | ???ms   | ???MB   | ???% |
  | free-threaded     | ???ms  | ???ms   | ???ms   | ???MB   | ???% |
  ```
- [ ] thread-safety 실험:
  - free-threaded에서 공유 자원 접근 시 race condition 재현
  - `threading.Lock`으로 해결
  - GIL이 숨겨주던 동시성 버그를 직접 경험
- [ ] 결론 정리:
  - 각 방식의 장단점
  - 언제 어떤 방식을 선택해야 하는가
  - free-threaded Python의 현재 한계와 전망

#### 결과물

- 완성된 프로젝트 (전체 기능 + 테스트 + 문서)
- 최종 벤치마크 리포트
- 동시성 방식 선택 가이드

---

## 5. 핵심 벤치마크 설계

### 테스트 대상 동시성 모델 4가지

```
┌─────────────────────────────────────────────────────┐
│  1. sync (순차)                                      │
│     for image in images:                             │
│         process(image)          # 하나씩 순서대로     │
├─────────────────────────────────────────────────────┤
│  2. threading + GIL=1 (기존 Python)                  │
│     Thread(target=process, args=(image,))            │
│     → GIL 때문에 실제로는 순차 실행됨                  │
├─────────────────────────────────────────────────────┤
│  3. multiprocessing                                  │
│     Process(target=process, args=(image,))           │
│     → 진짜 병렬이지만 프로세스 생성/IPC 오버헤드       │
├─────────────────────────────────────────────────────┤
│  4. threading + GIL=0 (free-threaded) ⭐             │
│     Thread(target=process, args=(image,))            │
│     → GIL 없이 진정한 멀티스레드 병렬 처리            │
└─────────────────────────────────────────────────────┘
```

### 측정 항목

| 항목 | 측정 방법 |
|------|----------|
| **처리 시간** | `time.perf_counter()` — 전체 배치 소요 시간 |
| **이미지당 시간** | 전체 시간 / 이미지 수 |
| **스레드별 스케일링** | 1, 2, 4, 8 스레드에서 처리 시간 변화 |
| **CPU 사용률** | `psutil.cpu_percent(percpu=True)` |
| **메모리 사용량** | `psutil.Process().memory_info().rss` |
| **스레드 안전성** | 공유 카운터 race condition 테스트 |

### 예상 결과 패턴

```
처리 시간 (낮을수록 좋음)
│
│  sync          ████████████████████████████  (기준선)
│  thread GIL=1  ████████████████████████████  (sync와 비슷하거나 약간 느림)
│  multiprocess  ██████████████                (빠르지만 오버헤드)
│  free-threaded ████████████                  (가장 빠름, 오버헤드 최소)
│
└─────────────────────────────────────────→ 스레드 수
```

---

## 6. 학습 방법

### Claude Code 활용 방식

각 Day마다 아래 순서로 진행:

1. **코드 읽기 요청** — "Day 2 시작할게. 먼저 SQLModel 사용법 간단히 설명해 줘"
2. **함께 코드 작성** — "image_router.py 만들어 줘. 각 단계마다 왜 이렇게 하는지 설명해 줘"
3. **실행 및 확인** — "서버 실행하고 /docs에서 테스트해 보자"
4. **테스트 작성** — "방금 만든 API 테스트 코드 작성해 줘"
5. **리뷰 및 개선** — "이 코드 리뷰해 줘. 개선할 점이 있어?"

### 핵심 원칙

- **직접 타이핑보다 이해가 중요**: Claude Code가 코드를 작성하더라도 각 줄의 의미를 이해하고 넘어가기
- **에러를 두려워하지 않기**: 에러가 나면 왜 나는지 함께 분석하는 것이 최고의 학습
- **벤치마크 결과에 집착하지 않기**: 숫자 자체보다 "왜 이런 결과가 나오는가"를 이해하는 것이 목표

---

## 7. 참고 자료

### Free-threaded Python

- [PEP 703 – Making the Global Interpreter Lock Optional in CPython](https://peps.python.org/pep-0703/)
- [Python 3.14 What's New: Free-threaded CPython](https://docs.python.org/3.14/whatsnew/3.14.html#free-threaded-cpython)
- [Python free-threading guide](https://docs.python.org/3.14/howto/free-threading-python.html)

### FastAPI

- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)
- [FastAPI 의존성 주입](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [FastAPI 보안 (OAuth2 + JWT)](https://fastapi.tiangolo.com/tutorial/security/)

### SQLModel

- [SQLModel 공식 문서](https://sqlmodel.tiangolo.com/)

### 기존 프로젝트 참고

- `grpc-diffusion-server/web-manager/` — FastAPI 구조, 라우터/서비스 패턴, 테스트 구조의 참고 원본

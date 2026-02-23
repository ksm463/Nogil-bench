# Day 6 진행 기록

> 날짜: 2026-02-23 (일)
> 단계: DB 동시성 실험 + PostgreSQL 도입

---

## 1. SQLite 동시성 한계 실험 (Stage 1)

### 목적

PostgreSQL을 도입하기 *전에*, SQLite가 왜 동시 쓰기에 약한지를 직접 체감한다.

### 실험 결과 (GIL=0, 스레드당 100행 INSERT)

**DELETE 저널 모드 (timeout=0.05s)**

| 스레드 | 예상 | 성공 | 잠금에러 | writes/s |
|--------|------|------|----------|----------|
| 1 | 100 | 100 | 0 | 167 |
| 2 | 200 | 189 | 11 | 169 |
| 4 | 400 | 334 | 66 | 175 |
| 8 | 800 | 515 | **285** | 172 |

**WAL 모드 (timeout=0.05s)**

| 스레드 | 예상 | 성공 | 잠금에러 | writes/s |
|--------|------|------|----------|----------|
| 1 | 100 | 100 | 0 | 268 |
| 4 | 400 | 347 | 53 | 248 |
| 8 | 800 | 614 | **186** | 360 |

**WAL 모드 (timeout=5s — 대기 허용)**

| 스레드 | 예상 | 성공 | 잠금에러 | writes/s |
|--------|------|------|----------|----------|
| 1 | 100 | 100 | 0 | 273 |
| 8 | 800 | 800 | 0 | 325 |

### 핵심 교훈

- **DELETE 모드**: 8스레드에서 35.6% 실패 — 파일 레벨 배타 잠금
- **WAL 모드**: 읽기+쓰기 동시 가능하지만 쓰기+쓰기는 여전히 직렬화
- **긴 timeout**: 에러는 없지만 writes/s가 스레드 수에 비례하지 않음

### 생성된 파일

```
src/scripts/bench_db_sqlite_limits.py   # SQLite 한계 실험 스크립트
tests/test_db_concurrency.py            # SQLite 동시성 테스트 (5개)
```

---

## 2. PostgreSQL 도입 (Stage 2)

### 구조

```
docker compose up -d
├── db (postgres:17-alpine)       # PostgreSQL 서버, 포트 5433
├── app (nogil-bench-compose)     # 앱 서버, 포트 8001
└── 기존 nogil-bench 컨테이너     # SQLite, 포트 8000 (정리 예정)
```

### database.py 재작성 — SQLite / PostgreSQL 분기

```python
def _build_engine():
    url = settings.DATABASE_URL

    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})

    # PostgreSQL: 커넥션 풀 설정이 핵심
    return create_engine(
        url,
        pool_size=settings.DB_POOL_SIZE,      # 상시 유지 커넥션 수
        max_overflow=settings.DB_MAX_OVERFLOW,  # 추가 허용 커넥션 수
        pool_pre_ping=True,                     # 사용 전 유효성 확인
        pool_recycle=300,                       # 5분 후 커넥션 재생성
    )
```

### 해결한 이슈

1. **`psycopg[binary]` 미지원**: free-threaded Python 3.14t에 바이너리 휠 없음 → pure Python `psycopg`로 전환
2. **포트 5432 충돌**: 호스트에 이미 PostgreSQL 존재 → 5433으로 매핑

### 수정/생성된 파일

| 파일 | 변경 |
|------|------|
| `docker-compose.yml` | ★ NEW — app + PostgreSQL 오케스트레이션 |
| `.env.example` | ★ NEW — 환경변수 문서화 |
| `pyproject.toml` | psycopg, psycopg-pool 추가 |
| `src/core/config.py` | DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_ECHO 추가 |
| `src/model/database.py` | SQLite/PostgreSQL 분기 + 커넥션 풀 설정 |
| `src/model/benchmark.py` | db_backend nullable 필드 추가 |
| `src/core/lifespan.py` | DB 타입/풀 설정 로깅 |
| `Dockerfile` | libpq5 런타임 의존성 추가 |
| `tests/conftest.py` | pg_engine fixture 추가 |

---

## 3. SQLite vs PostgreSQL 쓰기 벤치마크 (Stage 3)

### 목적

동일한 워크로드로 두 DB를 비교하여 MVCC의 가치를 정량적으로 확인한다.

### 결과 (GIL=0, 스레드당 100건 INSERT, WAL/timeout=5s)

| 스레드 | SQLite writes/s | PostgreSQL writes/s | PG/SQLite |
|--------|-----------------|---------------------|-----------|
| 1 | 260 | 487 | 1.9x |
| 2 | 298 | 773 | 2.6x |
| 4 | 226 | 1,543 | **6.8x** |
| 8 | 362 | 2,945 | **8.1x** |
| 16 | 425 | 4,794 | **11.3x** |

### 핵심 교훈

- **SQLite**: 스레드 1→16으로 늘려도 writes/s가 260→425 (1.6배) — 내부적으로 직렬화
- **PostgreSQL**: 487→4,794 (9.8배) — MVCC 덕분에 스레드에 비례하여 증가
- **16스레드 기준 PostgreSQL이 11.3배 빠름**

### 생성된 파일

```
src/scripts/bench_db_write.py   # SQLite vs PostgreSQL 동시 쓰기 벤치마크
```

---

## 4. 커넥션 풀 크기 실험 (Stage 4)

### 목적

pool_size가 왜 중요한지, 어떤 값이 적절한지 체감한다.

### 실험 설계

- 20개 동시 스레드, 스레드당 5회 쓰기
- max_overflow=0 (풀 크기 효과 격리)
- pool_size: 1, 5, 10, 20

### 결과

| pool_size | 시간 | writes/s | pool_size=1 대비 |
|-----------|------|----------|-----------------|
| 1 | 0.300s | 333 | 1x |
| 5 | 0.082s | 1,222 | 3.7x |
| 10 | 0.050s | 2,009 | 6.0x |
| 20 | 0.037s | 2,691 | **8.1x** |

### 핵심 교훈

- **pool_size=1**: 커넥션 1개를 20개 스레드가 돌려씀 → 333 w/s
- **1→5로만 늘려도 3.7배 개선** — 가장 효과가 큰 구간
- **10→20은 개선폭 감소** — 어느 시점부터 DB 서버 자체가 병목

### 실무 가이드

```
pool_size = 예상 동시 요청 수 (보통 5~20)
max_overflow = 트래픽 급증 대비 여유분 (보통 pool_size와 동일)
```

### 생성된 파일

```
src/scripts/bench_db_pool.py   # 커넥션 풀 크기 실험
```

---

## 5. 48조합 벤치마크 매트릭스 (Stage 5)

### 목적

Day 5의 16조합(10장)을 확장하여 이미지 수별 스케일링 데이터 확보.

### 결과 요약 (100장 기준, sync 대비 배율)

| 방식 | w=1 | w=2 | w=4 | w=8 |
|------|-----|-----|-----|-----|
| sync | 22.1s (기준) | — | — | — |
| threading | 24.0s (1.09x) | 11.5s (0.52x) | 6.6s (0.30x) | **4.1s (0.19x)** |
| multiprocessing | 31.4s (1.42x) | 18.9s (0.86x) | 13.3s (0.60x) | 11.7s (0.53x) |
| frethread | 22.0s (1.00x) | 11.5s (0.52x) | 6.5s (0.30x) | **4.2s (0.19x)** |

### 핵심 발견

1. **threading과 frethread가 거의 동일** — Pillow C 확장이 GIL을 자동 해제하기 때문
2. **워커 8개에서 sync 대비 5배 속도** (22s → 4.1s)
3. **multiprocessing이 가장 느림** — 프로세스 생성 + pickle 직렬화 오버헤드
4. **이미지가 많을수록 병렬화 이점 증가** — 10장 0.22x → 100장 0.19x

### PostgreSQL 동시성 테스트 (integration)

| 테스트 | 검증 |
|--------|------|
| `test_concurrent_writes_all_succeed` | 8스레드 동시 쓰기 전부 성공 (MVCC) |
| `test_pool_size_affects_throughput` | pool_size 1 vs 10 처리량 차이 확인 |

### 생성된 파일

```
src/scripts/bench_matrix_full.py         # 48조합 매트릭스
tests/test_db_concurrency.py             # ★ MODIFIED — PostgreSQL 테스트 2개 추가
```

---

## 6. 테스트 현황

### 단독 컨테이너 (nogil-bench, SQLite)

```
80 passed, 3 skipped (PostgreSQL 2개 + frethread GIL 1개)
Coverage: 93.75%
```

### Compose 컨테이너 (nogil-bench-compose, PostgreSQL)

```
# DB 동시성 테스트 (PostgreSQL 포함)
TEST_DATABASE_URL=... uv run pytest tests/test_db_concurrency.py
→ 7 passed
```

### 테스트 파일 요약

| 파일 | 수 | 내용 |
|------|-----|------|
| test_db_concurrency.py | 7 | SQLite 잠금(5) + PostgreSQL MVCC(2) |
| test_runners.py | 11 | 4개 러너 동작 + 일관성 |
| test_benchmark_router.py | 15 | 벤치마크 API CRUD |
| test_job_router.py | 16 | 배치 작업 API |
| test_integration.py | 3 | 전체 플로우 검증 |
| (기존 Day 4) | 31 | auth, image, error, operations, security |

---

## 7. Day 6 완료 체크리스트

- [x] SQLite 동시성 한계 실험 — DELETE/WAL 모드 비교, 잠금 에러 재현
- [x] PostgreSQL 도입 — docker-compose, 커넥션 풀, database.py 분기
- [x] SQLite vs PostgreSQL 쓰기 벤치마크 — 16스레드에서 11.3배 차이 확인
- [x] 커넥션 풀 크기 실험 — pool_size 1→20에서 8.1배 차이 확인
- [x] 48조합 벤치마크 매트릭스 — 3 이미지 수 × 4 워커 × 4 방식
- [x] PostgreSQL 동시성 테스트 — MVCC 동시 쓰기 + 풀 처리량 차이
- [x] 전체 테스트 80개 통과, 커버리지 94%

---

## 8. 현재 프로젝트 구조

```
src/
├── main.py
├── core/
│   ├── config.py                       # ★ MODIFIED — DB 풀 설정 추가
│   ├── lifespan.py                     # ★ MODIFIED — DB 타입/풀 로깅
│   ├── security.py
│   ├── dependencies.py
│   ├── middleware.py
│   ├── exceptions.py
│   └── error_handlers.py
├── model/
│   ├── database.py                     # ★ MODIFIED — SQLite/PostgreSQL 분기
│   ├── user.py
│   ├── image.py
│   ├── benchmark.py                    # ★ MODIFIED — db_backend 필드 추가
│   └── job.py
├── processor/
│   ├── operations.py
│   ├── sync_runner.py
│   ├── async_runner.py
│   ├── thread_runner.py
│   ├── mp_runner.py
│   └── frethread_runner.py
├── router/
│   ├── auth_router.py
│   ├── image_router.py
│   ├── benchmark_router.py
│   └── job_router.py
├── service/
│   ├── auth_service.py
│   ├── image_service.py
│   ├── benchmark_service.py
│   └── job_service.py
├── utility/
│   ├── logger.py
│   └── timer.py
└── scripts/
    ├── bench_gil.py
    ├── bench_baseline.py
    ├── bench_async.py
    ├── bench_concurrency.py
    ├── bench_matrix.py
    ├── bench_matrix_full.py            # ★ NEW — 48조합 매트릭스
    ├── bench_db_sqlite_limits.py       # ★ NEW — SQLite 한계 실험
    ├── bench_db_write.py               # ★ NEW — SQLite vs PostgreSQL 쓰기
    ├── bench_db_pool.py                # ★ NEW — 커넥션 풀 실험
    └── test_operations.py

tests/
├── conftest.py                         # ★ MODIFIED — pg_engine fixture
├── test_db_concurrency.py              # ★ NEW — DB 동시성 테스트 (7개)
├── test_runners.py
├── test_benchmark_router.py
├── test_job_router.py
├── test_integration.py
├── test_security.py
├── test_operations.py
├── test_auth_router.py
├── test_image_router.py
├── test_error_responses.py
└── fixtures/

docker-compose.yml                      # ★ NEW — app + PostgreSQL
.env.example                            # ★ NEW — 환경변수 문서화
Dockerfile                              # ★ MODIFIED — libpq5 추가
pyproject.toml                          # ★ MODIFIED — psycopg, psycopg-pool
```

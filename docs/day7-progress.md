# Day 7 진행 기록

> 날짜: 2026-02-24 (월)
> 단계: 통합 + 최종 마무리

---

## 1. API 문서 정리 (Stage 1)

### 작업 내용

모든 엔드포인트에 Swagger 문서를 강화했다.

- 17개 엔드포인트에 `summary`, `description`, `responses` 추가
- `ErrorResponse` 공통 스키마 생성 → 에러 응답(401, 403, 404, 422) 명세
- FastAPI 앱 메타데이터 강화 (description, contact, swagger_ui_parameters)
- 커스텀 OpenAPI 스키마에 JWT Bearer 인증 추가 → Swagger UI Authorize 버튼

### 정적 Swagger 문서

GitHub Pages용 정적 Swagger UI를 생성했다.

| 파일 | 설명 |
|------|------|
| `src/core/openapi.py` | JWT Bearer securityScheme 추가 |
| `src/scripts/export_openapi.py` | OpenAPI JSON + Swagger UI HTML 생성 스크립트 |
| `swagger/openapi.json` | OpenAPI 3.1 스펙 (17 endpoints, 12 schemas) |
| `swagger/index.html` | Swagger UI 정적 HTML |

---

## 2. 코드 자가 리뷰 (Stage 2)

### 체크리스트

- [x] 모든 보호 대상 엔드포인트에 `Depends(get_current_user)` 적용 확인 (15개)
- [x] 입력 유효성 검증 — `Literal` 타입으로 method/operation 제한, 패스워드 `min_length=8`
- [x] 에러 응답 일관성 — `ErrorResponse` 스키마로 통일
- [x] 로그에 민감 정보(패스워드, 토큰) 노출 없음
- [x] Ruff 린팅 통과 — `ruff`를 dev 의존성에 추가, line-length=100

### 주요 변경

| 파일 | 변경 |
|------|------|
| `pyproject.toml` | ruff dev 의존성, line-length=100, ignore N818, per-file-ignores |
| `src/router/benchmark_router.py` | method/operation에 `Literal` 타입 적용 |
| `src/router/job_router.py` | 동일 |
| `src/router/image_router.py` | operation에 `Literal`, params `dict \| None` |
| `src/router/auth_router.py` | password `min_length=8` |

---

## 3. README.md + Swagger 문서 (Stage 3)

### 작업 내용

- README.md 전면 재작성 — 프로젝트 개요, 기술 스택, 빠른 시작, 구조, API 목록, 벤치마크 결과
- GitHub Pages Swagger UI 링크 포함
- grpc-diffusion-server 프로젝트의 패턴을 참고하여 export_openapi.py 작성

---

## 4. 최종 벤치마크 리포트 (Stage 4)

### 작업 내용

Day 1~6의 모든 벤치마크 데이터를 `docs/day7-benchmark-report.md`에 종합했다.

| 섹션 | 내용 |
|------|------|
| CPU-bound 동시성 | GIL=0 vs GIL=1, 순수 Python vs C 확장, asyncio |
| 이미지 처리 매트릭스 | 10장/100장, 4방식 × 4워커, GIL 유무 비교 |
| DB 동시성 | SQLite 한계, SQLite vs PostgreSQL, 커넥션 풀 |
| 종합 가이드 | 동시성 방식 선택 기준, 핵심 숫자, 가치와 한계 |

---

## 5. Thread-Safety 실험 (Stage 5)

### 목적

GIL이 숨겨주던 동시성 버그를 free-threaded Python에서 직접 재현하고,
`threading.Lock`으로 해결하는 과정을 보여준다.

### 실험 결과 (GIL=0, 8스레드)

**실험 1-2: 공유 카운터 (8스레드 × 100,000회 증가, 기댓값 800,000)**

| 조건 | 결과 | 비고 |
|------|------|------|
| Lock 없음 | ~150,000 (81% 손실) | read-modify-write 사이 끼어들기 |
| Lock 사용 | 800,000 (정확) | critical section 보호 |

**실험 3-4: Check-then-act (limit=100,000)**

| 조건 | 결과 | 비고 |
|------|------|------|
| Lock 없음 | limit 초과 가능 | check와 act 사이 TOCTOU 경합 |
| Lock 사용 | limit 정확 준수 | check-act를 원자적 블록으로 |

### 핵심 교훈

- **GIL=1**: race condition이 드러나지 않지만 "우연히 안전한 것"일 뿐
- **GIL=0**: 진짜 병렬 실행이므로 즉시 버그가 드러남
- **해결**: `threading.Lock`으로 공유 상태 변경 구간을 보호

### 생성된 파일

```
src/scripts/bench_thread_safety.py   # Thread-safety 벤치마크 스크립트
tests/test_thread_safety.py          # Thread-safety pytest 테스트 (6개)
```

---

## 6. 결론 정리 (Stage 6)

### 동시성 방식 선택 가이드

| 상황 | 추천 방식 | 이유 |
|------|----------|------|
| C 확장 CPU-bound (Pillow, NumPy) | threading | GIL 유무 무관, 오버헤드 최소 |
| 순수 Python CPU-bound | frethread (GIL=0) | GIL=0에서만 진정한 병렬 |
| 순수 Python CPU-bound + GIL=1 | multiprocessing | GIL 우회 유일한 방법 |
| I/O-bound (네트워크, 파일) | asyncio / threading | await 양보로 동시성 확보 |
| DB 동시 쓰기 | PostgreSQL + 커넥션 풀 | MVCC로 진짜 병렬 쓰기 |
| 공유 상태 변경 | threading.Lock | race condition 방지 필수 |

### 핵심 숫자 요약

| 실험 | 비교 | 차이 |
|------|------|------|
| GIL=0 threading vs GIL=1 threading | 순수 Python fib(34)×4 | **3.6배** |
| threading w=8 vs sync | 100장 blur | **5.4배** |
| PostgreSQL vs SQLite | 16스레드 동시 쓰기 | **11.3배** |
| pool_size=20 vs pool_size=1 | 20스레드 동시 쓰기 | **8.1배** |
| Lock 없음 vs Lock 사용 | 공유 카운터 8스레드 | **81% 값 손실 vs 정확** |

### free-threaded Python의 가치

**가치가 명확한 경우:**
- 순수 Python CPU-bound 작업에서 threading이 multiprocessing을 대체 (오버헤드 훨씬 적음)
- GIL=0 + threading으로 프로세스 생성/IPC 오버헤드 없이 진짜 병렬
- 단, 공유 상태에 대한 Lock이 필수 — GIL이 해주던 암묵적 보호가 사라짐

**가치가 제한적인 경우:**
- C 확장 위주 작업 (Pillow, NumPy) — 이미 GIL을 릴리즈하므로 차이 적음
- I/O-bound 작업 — asyncio로 충분

**현재 한계 (2026년 2월 기준):**
- 일부 C 확장 패키지에 free-threaded 휠 미제공 (`psycopg[binary]` 등)
- `multiprocessing`의 `fork()`가 multi-threaded 프로세스에서 deadlock 경고
- 생태계 전반의 thread-safety 검증이 아직 진행 중
- Lock을 사용하면 해당 구간은 직렬화되므로 병렬 이점이 감소 — Lock 범위 최소화가 중요

---

## 7. 테스트 현황

```
86 passed, 3 skipped
Coverage: 92.53%
Ruff: All checks passed
```

### 테스트 파일 요약

| 파일 | 수 | 내용 |
|------|-----|------|
| test_auth_router.py | 8 | 회원가입, 로그인, 토큰 검증 |
| test_image_router.py | 12 | 이미지 CRUD + 처리 |
| test_benchmark_router.py | 15 | 벤치마크 API CRUD |
| test_job_router.py | 16 | 배치 작업 API |
| test_runners.py | 11 | 4개 러너 동작 + 일관성 |
| test_db_concurrency.py | 7 | SQLite 잠금 + PostgreSQL MVCC |
| test_thread_safety.py | 6 | race condition + Lock 검증 |
| test_integration.py | 3 | 전체 플로우 |
| test_error_responses.py | 3 | 에러 응답 형식 |
| test_operations.py | 2 | 이미지 처리 함수 |
| test_security.py | 3 | JWT, 해싱 |

---

## 8. Day 7 완료 체크리스트

- [x] API 문서 정리 — summary/description/responses, Swagger UI
- [x] 코드 자가 리뷰 — 인증, 유효성 검증, ruff 린팅
- [x] README.md + 정적 Swagger 문서
- [x] 최종 벤치마크 리포트 — Day 1~6 데이터 종합
- [x] Thread-safety 실험 — race condition 재현, Lock 해결
- [x] 결론 정리 — 동시성 선택 가이드, 핵심 숫자, 가치와 한계

---

## 9. 최종 프로젝트 구조

```
src/
├── main.py                          # ★ MODIFIED — 앱 메타데이터, OpenAPI 커스텀
├── core/
│   ├── config.py
│   ├── lifespan.py
│   ├── security.py
│   ├── dependencies.py
│   ├── middleware.py
│   ├── exceptions.py                # ★ MODIFIED — ErrorResponse 추가
│   ├── error_handlers.py
│   └── openapi.py                   # ★ NEW — JWT Bearer OpenAPI 스키마
├── model/
│   ├── database.py
│   ├── user.py
│   ├── image.py
│   ├── benchmark.py
│   └── job.py
├── processor/
│   ├── operations.py
│   ├── sync_runner.py
│   ├── thread_runner.py
│   ├── mp_runner.py
│   └── frethread_runner.py
├── router/
│   ├── auth_router.py               # ★ MODIFIED — docs, min_length
│   ├── image_router.py              # ★ MODIFIED — docs, Literal, params
│   ├── benchmark_router.py          # ★ MODIFIED — docs, Literal
│   └── job_router.py                # ★ MODIFIED — docs, Literal
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
    ├── bench_matrix_full.py
    ├── bench_db_sqlite_limits.py
    ├── bench_db_write.py
    ├── bench_db_pool.py
    ├── bench_thread_safety.py       # ★ NEW — thread-safety 실험
    ├── export_openapi.py            # ★ NEW — Swagger 문서 생성
    └── test_operations.py

tests/
├── conftest.py
├── test_auth_router.py              # ★ MODIFIED — min_length 대응
├── test_image_router.py
├── test_benchmark_router.py         # ★ MODIFIED — Literal 422 대응
├── test_job_router.py               # ★ MODIFIED — Literal 422 대응
├── test_error_responses.py          # ★ MODIFIED — Literal/min_length 대응
├── test_runners.py
├── test_db_concurrency.py
├── test_thread_safety.py            # ★ NEW — race condition 테스트
├── test_integration.py
├── test_security.py
├── test_operations.py
└── fixtures/

swagger/
├── openapi.json                     # ★ NEW — OpenAPI 3.1 스펙
└── index.html                       # ★ NEW — Swagger UI

docs/
├── day1-progress.md
├── day2-progress.md
├── day3-progress.md
├── day4-progress.md
├── day5-progress.md
├── day6-progress.md
├── day7-progress.md                 # ★ NEW — 이 문서
├── day7-benchmark-report.md         # ★ NEW — 최종 벤치마크 리포트
├── day6-study-guide.md
└── nogil-bench-project-guide.md
```

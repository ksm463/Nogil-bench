# Day 5 진행 기록

> 날짜: 2026-02-23 (일)
> 단계: Free-threaded 실험 + 배치 API + 벤치마크 API ⭐ 핵심 Day

---

## 1. 러너 모듈 정리 (4가지 동시성 방식)

### 생성된 파일

```
src/processor/
├── sync_runner.py          # (기존) 순차 처리 기준선
├── async_runner.py         # (기존) asyncio 러너
├── thread_runner.py        # ★ NEW — threading + GIL
├── mp_runner.py            # ★ NEW — multiprocessing
├── frethread_runner.py     # ★ NEW — threading + GIL=0 (free-threaded)
```

### 공통 인터페이스

```python
# sync_runner (workers 없음)
run(image_paths: list[str], operation: str, params: dict | None = None) -> list[Image]

# thread_runner / mp_runner / frethread_runner
run(image_paths: list[str], operation: str, params: dict | None = None, workers: int = 4) -> list[Image]
```

모든 러너가 동일한 입출력 구조를 가지므로 벤치마크에서 러너만 교체하면 된다.

### 러너별 구현 특징

| 러너 | 핵심 구현 | 주의사항 |
|------|----------|---------|
| `thread_runner` | `ThreadPoolExecutor` + `pool.map` | GIL=1에서 순수 Python CPU-bound 병렬 불가 |
| `mp_runner` | `ProcessPoolExecutor` + `fork` context | 처리 함수가 모듈 최상위에 있어야 pickle 가능 |
| `frethread_runner` | `ThreadPoolExecutor` (thread_runner와 동일) | `sys._is_gil_enabled()` 검증 — GIL=1이면 RuntimeError |

### mp_runner의 pickle 문제 해결

```python
# ProcessPoolExecutor는 워커에 함수를 pickle로 전달한다.
# 람다나 로컬 함수는 pickle 불가 → 모듈 최상위에 정의해야 한다.

# 설정 전달: initializer 패턴
def _init_worker(operation, params):
    global _operation, _params
    _operation = operation
    _params = params

ProcessPoolExecutor(initializer=_init_worker, initargs=(operation, params))
```

---

## 2. 벤치마크 API

### API 엔드포인트

| 메서드 | 경로 | 동작 | 상태코드 |
|--------|------|------|---------|
| POST | `/api/benchmarks/run` | 벤치마크 실행 + 결과 저장 | 201 |
| GET | `/api/benchmarks/` | 내 결과 목록 | 200 |
| GET | `/api/benchmarks/{id}` | 결과 상세 | 200 |
| GET | `/api/benchmarks/compare` | 여러 결과 비교 (`?ids=1&ids=2`) | 200 |

### 생성된 파일

```
src/model/benchmark.py           # ★ NEW — BenchmarkResult 모델
src/service/benchmark_service.py # ★ NEW — 실행 + CRUD
src/router/benchmark_router.py   # ★ NEW — 4개 엔드포인트
```

### BenchmarkResult 모델

```python
class BenchmarkResult(SQLModel, table=True):
    id: int | None
    method: str           # sync, threading, multiprocessing, frethread
    operation: str        # blur, resize, grayscale, ...
    workers: int
    image_count: int
    duration: float       # seconds
    gil_enabled: bool     # 실행 시점의 GIL 상태
    user_id: int
    created_at: datetime
```

### 요청 예시

```json
POST /api/benchmarks/run
{
    "method": "frethread",
    "operation": "blur",
    "workers": 4,
    "image_count": 10,
    "params": {"radius": 10}
}
```

---

## 3. 배치 처리 API

### API 엔드포인트

| 메서드 | 경로 | 동작 | 상태코드 |
|--------|------|------|---------|
| POST | `/api/jobs/batch` | 배치 작업 생성 (즉시 반환) | 202 Accepted |
| GET | `/api/jobs/` | 내 작업 목록 | 200 |
| GET | `/api/jobs/{job_id}` | 작업 상태 조회 | 200 |
| GET | `/api/jobs/{job_id}/result` | 완료된 결과 조회 | 200 |

### 생성된 파일

```
src/model/job.py           # ★ NEW — Job 모델
src/service/job_service.py # ★ NEW — 작업 생성 + 백그라운드 처리
src/router/job_router.py   # ★ NEW — 4개 엔드포인트
```

### Job 모델

```python
class Job(SQLModel, table=True):
    id: int | None
    user_id: int
    status: str            # queued → processing → completed / failed
    method: str            # sync, threading, multiprocessing, frethread
    operation: str
    params: str            # JSON string
    workers: int
    image_ids: str         # JSON string: [1, 2, 3]
    image_count: int
    processed_count: int   # 진행률 추적
    duration: float | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
```

### 배치 처리 흐름

```
1. POST /api/jobs/batch
   - 이미지 소유권 검증
   - Job 레코드 생성 (status=queued)
   - BackgroundTasks에 process_job 등록
   - 202 Accepted + job 데이터 즉시 반환

2. BackgroundTasks가 process_job 실행
   - 별도 DB 세션으로 처리 (요청 세션과 분리)
   - 이미지별 처리 → processed_count 업데이트
   - 완료 시 status=completed, duration 기록
   - 실패 시 status=failed, error_message 기록

3. GET /api/jobs/{id} → 상태 확인
4. GET /api/jobs/{id}/result → 처리된 이미지 목록
```

### BackgroundTasks 테스트 이슈 해결

`process_job`이 `Session(engine)`으로 별도 세션을 열어 작업하는데,
테스트의 in-memory SQLite와 프로덕션 엔진이 분리되는 문제가 발생했다.

```python
# service/job_service.py — 테스트 시 엔진 오버라이드 가능
_engine = None

def get_engine():
    return _engine or default_engine

# tests/conftest.py — 테스트 엔진 주입
job_service._engine = engine  # in-memory SQLite 엔진
```

---

## 4. 벤치마크 매트릭스 결과

### 실행 환경

```
Python 3.14.3 free-threading build
이미지: 10장 Pillow blur (radius=10)
워커 수: 1, 2, 4, 8
```

### GIL=0 (free-threaded) 결과

| 방식 | w=1 | w=2 | w=4 | w=8 |
|------|-----|-----|-----|-----|
| sync | 2.40s (기준) | - | - | - |
| threading | 2.36s (0.98x) | 1.23s (0.51x) | 0.76s (0.32x) | 0.58s (0.24x) |
| frethread | 2.50s (1.04x) | 1.39s (0.58x) | 0.74s (0.31x) | **0.52s (0.22x)** |
| multiprocessing | 3.57s (1.49x) | 2.02s (0.84x) | 1.50s (0.63x) | 1.62s (0.68x) |

### GIL=1 (기존 Python) 결과

| 방식 | w=1 | w=2 | w=4 | w=8 |
|------|-----|-----|-----|-----|
| sync | 2.39s (기준) | - | - | - |
| threading | 2.39s (1.00x) | 1.27s (0.53x) | 0.79s (0.33x) | **1.34s (0.56x)** |
| multiprocessing | 3.45s (1.44x) | 1.99s (0.83x) | 1.44s (0.60x) | 1.62s (0.68x) |

### 핵심 발견

1. **w=8에서 GIL 차이가 극명**
   - GIL=1: threading w=8 → **1.34s** (w=4보다 느려짐! GIL 경합)
   - GIL=0: frethread w=8 → **0.52s** (계속 스케일링)
   - 워커를 늘릴수록 GIL=1은 경합으로 성능 저하, GIL=0은 선형 향상

2. **Pillow blur는 C 확장이라 w=4까지는 GIL 영향이 적음**
   - C 확장은 내부에서 GIL을 릴리즈하므로 GIL=0/1 차이가 작음
   - 그러나 w=8처럼 스레드가 많아지면 GIL 재획득 경합이 발생

3. **multiprocessing은 전반적으로 느림**
   - 프로세스 생성 오버헤드 + IPC 비용이 스레드보다 큼
   - w=8에서 되려 느려짐 (프로세스 수 > CPU 코어 수)

4. **free-threaded의 진짜 가치**: 워커 수를 늘려도 성능이 계속 향상
   - GIL=1은 특정 지점 이후 경합으로 역전
   - GIL=0은 CPU 코어 수까지 거의 선형 스케일링

---

## 5. 테스트 현황

### 실행 결과

```
$ docker exec nogil-bench uv run pytest

75 passed, 1 skipped in 46.49s
Coverage: 93.97%
```

### 테스트 카테고리별 요약

| 파일 | 테스트 수 | 검증 내용 |
|------|-----------|----------|
| test_runners.py | 11 | 4개 러너 동작 + 일관성 비교 |
| test_benchmark_router.py | 15 | 벤치마크 run/list/detail/compare + 에러 케이스 |
| test_job_router.py | 16 | 배치 생성/완료/목록/상태/결과 + 소유권/에러 |
| test_integration.py | 3 | 배치 전체 플로우, 벤치마크 전체 플로우, 4방식 동시 실행 |
| (기존 Day 4) | 31 | auth, image, error, operations, security |

### 신규 테스트 상세

**test_runners.py (11개)**

| 카테고리 | 수 | 내용 |
|---|---|---|
| SyncRunner | 2 | blur 반환값, resize 크기 검증 |
| ThreadRunner | 3 | blur, resize, single worker 엣지 케이스 |
| MpRunner | 2 | blur, resize (pickle 직렬화 검증) |
| FrethreadRunner | 3 | GIL 검증, blur, resize (1 skipped: GIL=0 환경) |
| Consistency | 1 | 3개 러너 동일 결과 확인 |

**test_benchmark_router.py (15개)**

| 카테고리 | 수 | 내용 |
|---|---|---|
| Run | 7 | sync/threading/mp/frethread 성공, invalid method 400, invalid operation 400, 미인증 401 |
| List | 3 | 빈 목록, 실행 후 1건, 타인 결과 안 보임 |
| Detail | 3 | 상세 조회, 없는 ID 404, 타인 것 404 |
| Compare | 2 | 2건 비교, 없는 ID 404 |

**test_job_router.py (16개)**

| 카테고리 | 수 | 내용 |
|---|---|---|
| Batch 생성 | 8 | 단일/복수 이미지, 백그라운드 완료, 없는 이미지 404, 타인 이미지 403, invalid method/operation 400, 미인증 401 |
| List | 3 | 빈 목록, 실행 후 1건, 타인 작업 안 보임 |
| Status | 3 | 상태 조회, 없는 ID 404, 타인 작업 404 |
| Result | 2 | 완료된 결과 조회, 없는 작업 404 |

**test_integration.py (3개)**

| 테스트 | 검증 플로우 |
|---|---|
| test_full_batch_flow | upload → batch → status=completed → result (output_path 확인) |
| test_run_and_compare | benchmark run x2 → list 2건 → compare → detail |
| test_all_four_methods | sync/threading/mp/frethread 4방식 모두 실행 → compare 4건 |

---

## 6. 추가된 예외 클래스

```python
# core/exceptions.py에 추가
BenchmarkNotFound    # 404 BENCHMARK_NOT_FOUND
InvalidMethod        # 400 INVALID_METHOD
JobNotFound          # 404 JOB_NOT_FOUND
JobNotCompleted      # 400 JOB_NOT_COMPLETED
```

---

## 7. Day 5 완료 체크리스트

- [x] `processor/thread_runner.py` — threading + GIL 러너
- [x] `processor/mp_runner.py` — multiprocessing 러너
- [x] `processor/frethread_runner.py` — free-threaded 러너
- [x] `model/benchmark.py` — 벤치마크 결과 모델
- [x] `service/benchmark_service.py` — 벤치마크 실행 + CRUD
- [x] `router/benchmark_router.py` — run/list/detail/compare API
- [x] `model/job.py` — 배치 작업 모델
- [x] `service/job_service.py` — 작업 생성 + BackgroundTasks 처리
- [x] `router/job_router.py` — batch/list/status/result API
- [x] `scripts/bench_matrix.py` — 4방식 × 워커 수 벤치마크 스크립트
- [x] 통합 테스트 — 전체 플로우 검증
- [x] 4가지 벤치마크 매트릭스 실행 — GIL=0 / GIL=1 결과 확보
- [x] 커스텀 예외 4개 추가 (BenchmarkNotFound, InvalidMethod, JobNotFound, JobNotCompleted)
- [x] main.py에 benchmark_router, job_router 등록
- [x] 전체 테스트 75개 통과, 커버리지 94%

---

## 8. 현재 프로젝트 구조

```
src/
├── main.py                         # ★ MODIFIED — benchmark_router, job_router 추가
├── core/
│   ├── config.py
│   ├── lifespan.py
│   ├── security.py
│   ├── dependencies.py
│   ├── middleware.py
│   ├── exceptions.py               # ★ MODIFIED — 벤치마크/작업 예외 4개 추가
│   └── error_handlers.py
├── model/
│   ├── database.py
│   ├── user.py
│   ├── image.py
│   ├── benchmark.py                # ★ NEW — BenchmarkResult
│   └── job.py                      # ★ NEW — Job (배치 작업)
├── processor/
│   ├── operations.py
│   ├── sync_runner.py
│   ├── async_runner.py
│   ├── thread_runner.py            # ★ NEW — threading
│   ├── mp_runner.py                # ★ NEW — multiprocessing
│   └── frethread_runner.py         # ★ NEW — free-threaded
├── router/
│   ├── auth_router.py
│   ├── image_router.py
│   ├── benchmark_router.py         # ★ NEW — 벤치마크 API
│   └── job_router.py               # ★ NEW — 배치 작업 API
├── service/
│   ├── auth_service.py
│   ├── image_service.py
│   ├── benchmark_service.py        # ★ NEW — 벤치마크 서비스
│   └── job_service.py              # ★ NEW — 작업 서비스
├── utility/
│   ├── logger.py
│   └── timer.py
└── scripts/
    ├── bench_gil.py
    ├── bench_baseline.py
    ├── bench_async.py
    ├── bench_concurrency.py
    ├── bench_matrix.py             # ★ NEW — 4방식 × 워커 수 매트릭스
    └── test_operations.py

tests/
├── __init__.py
├── conftest.py                     # ★ MODIFIED — job_service 엔진 오버라이드
├── test_security.py                # 3개
├── test_operations.py              # 3개
├── test_auth_router.py             # 8개
├── test_image_router.py            # 13개
├── test_error_responses.py         # 4개
├── test_runners.py                 # ★ NEW — 11개
├── test_benchmark_router.py        # ★ NEW — 15개
├── test_job_router.py              # ★ NEW — 16개
├── test_integration.py             # ★ NEW — 3개
└── fixtures/
    ├── test_cat.png
    ├── test_landscape.png
    ├── test_portrait.png
    ├── test_text.png
    └── output/
```

# 최종 벤치마크 리포트

> 날짜: 2026-02-24 (월)
> 환경: Python 3.14.3 free-threading build, Docker, `PYTHON_GIL=0`

---

## 1. 실험 개요

이 리포트는 7일간 수행한 모든 벤치마크 데이터를 종합한다.

| 실험 | Day | 스크립트 | 측정 대상 |
|------|-----|---------|----------|
| GIL=0 vs GIL=1 | 1 | bench_gil.py | 순수 Python CPU-bound (fib) |
| 이미지 처리 기준선 | 2 | bench_baseline.py | 6가지 operation 순차 처리 |
| asyncio vs sync | 3 | bench_async.py | CPU-bound에서 async의 한계 |
| 동시성 3종 비교 | 4 | bench_concurrency.py | threading vs multiprocessing (GIL 유무) |
| 4방식 매트릭스 (10장) | 5 | bench_matrix.py | 4방식 × 4워커 × GIL 유무 |
| 48조합 매트릭스 | 6 | bench_matrix_full.py | 4방식 × 4워커 × 3이미지 수 |
| SQLite 한계 실험 | 6 | bench_db_sqlite_limits.py | SQLite 동시 쓰기 잠금 |
| SQLite vs PostgreSQL | 6 | bench_db_write.py | 동시 쓰기 처리량 비교 |
| 커넥션 풀 크기 | 6 | bench_db_pool.py | pool_size별 처리량 |

---

## 2. CPU-bound 동시성 비교

### 2-1. GIL=0 vs GIL=1 — 순수 Python (Day 1)

> 재귀 피보나치 `fib(34)` × 4회, 4스레드

| | Sequential | Threaded (4) | Speedup |
|---|---|---|---|
| **GIL=0** | 3.58s | 1.13s | **3.17x** |
| **GIL=1** | 3.55s | 4.03s | **0.88x** |

- GIL=1: 스레드를 써도 **오히려 느림** (경합 + 컨텍스트 스위칭)
- GIL=0: 4스레드로 **3.17배** 빨라짐 — 진짜 병렬

### 2-2. 순수 Python vs C 확장 (Day 4)

> 10개 태스크, 4 workers

**순수 Python CPU-bound (재귀 피보나치)**

| 방식 | GIL=1 | GIL=0 |
|------|-------|-------|
| sync | 2.26s (1.00x) | 2.20s (1.00x) |
| threading (4) | 2.50s (1.10x) | **0.71s (0.32x)** |
| multiprocessing (4) | 0.71s (0.32x) | 0.69s (0.31x) |

**Pillow blur (C 확장)**

| 방식 | GIL=1 | GIL=0 |
|------|-------|-------|
| sync | 2.52s (1.00x) | 2.47s (1.00x) |
| threading (4) | 0.79s (0.31x) | 0.80s (0.32x) |
| multiprocessing (4) | 0.89s (0.35x) | 0.87s (0.35x) |

핵심:
- **순수 Python**: GIL=0에서만 threading이 효과적 (GIL=1은 역효과)
- **C 확장**: GIL과 무관하게 threading이 빠름 (내부에서 GIL 릴리즈)
- **multiprocessing**: GIL 무관하게 항상 빠르지만 프로세스 오버헤드

### 2-3. asyncio 실험 (Day 3)

> 10장 blur, GIL=0

| 방식 | 시간 | 배율 |
|------|------|------|
| sync | 2.486s | 1.00x |
| async (pure) | 2.276s | 0.92x |
| executor (1 worker) | 2.375s | 0.96x |
| executor (2 workers) | 1.263s | 0.51x |
| executor (4 workers) | 0.763s | 0.31x |

- **async (pure)는 sync와 동일**: CPU-bound에서는 await 양보 시점이 없음
- **run_in_executor**: 스레드풀 위임 → GIL=0이므로 워커 수에 비례하여 빨라짐

---

## 3. 이미지 처리 매트릭스 (Day 5 + Day 6)

### 3-1. 10장 기준 (Day 5, GIL=0)

| 방식 | w=1 | w=2 | w=4 | w=8 |
|------|-----|-----|-----|-----|
| sync | 2.40s | — | — | — |
| threading | 2.36s (0.98x) | 1.23s (0.51x) | 0.76s (0.32x) | 0.58s (0.24x) |
| frethread | 2.50s (1.04x) | 1.39s (0.58x) | 0.74s (0.31x) | **0.52s (0.22x)** |
| multiprocessing | 3.57s (1.49x) | 2.02s (0.84x) | 1.50s (0.63x) | 1.62s (0.68x) |

### 3-2. GIL=0 vs GIL=1 (Day 5, 10장)

| 방식 (w=8) | GIL=0 | GIL=1 |
|------------|-------|-------|
| threading | 0.58s | **1.34s** (w=4의 0.79s보다 느림!) |
| frethread | **0.52s** | — (GIL=0 전용) |
| multiprocessing | 1.62s | 1.62s (GIL 무관) |

- GIL=1에서 w=8 threading이 **w=4보다 느려지는 역전** 발생 (GIL 경합)
- GIL=0은 w=8까지 계속 스케일링

### 3-3. 48조합 매트릭스 — 100장 기준 (Day 6, GIL=0)

| 방식 | w=1 | w=2 | w=4 | w=8 |
|------|-----|-----|-----|-----|
| sync | 22.1s (기준) | — | — | — |
| threading | 24.0s (1.09x) | 11.5s (0.52x) | 6.6s (0.30x) | **4.1s (0.19x)** |
| multiprocessing | 31.4s (1.42x) | 18.9s (0.86x) | 13.3s (0.60x) | 11.7s (0.53x) |
| frethread | 22.0s (1.00x) | 11.5s (0.52x) | 6.5s (0.30x) | **4.2s (0.19x)** |

### 3-4. 이미지 수별 스케일링 (w=8, sync 대비 비율)

| 방식 | 10장 | 100장 | 스케일링 효과 |
|------|------|-------|-------------|
| threading | 0.24x | **0.19x** | 이미지 많을수록 유리 |
| frethread | 0.22x | **0.19x** | 동일 |
| multiprocessing | 0.68x | 0.53x | 개선되지만 여전히 느림 |

### 3-5. 이미지 처리 종합 결론

```
                처리 시간 (100장 blur, w=8)
    sync        ████████████████████████████████████████  22.1s
    threading   ███████                                    4.1s (5.4x 빠름)
    frethread   ████████                                   4.2s (5.3x 빠름)
    mp          █████████████████████                      11.7s (1.9x 빠름)
```

1. **threading ≈ frethread**: Pillow가 C 확장이라 GIL을 자동 릴리즈 → GIL 유무 영향 적음
2. **워커 8개에서 sync 대비 5배** 속도
3. **multiprocessing이 가장 느림**: 프로세스 생성 + pickle 직렬화 오버헤드
4. **이미지가 많을수록 병렬화 이점 증가** (오버헤드 비율 감소)

---

## 4. DB 동시성 비교 (Day 6)

### 4-1. SQLite 동시 쓰기 한계

> GIL=0, 스레드당 100행 INSERT

**DELETE 저널 모드 (timeout=0.05s)**

| 스레드 | 예상 | 성공 | 잠금에러 | 실패율 |
|--------|------|------|----------|--------|
| 1 | 100 | 100 | 0 | 0% |
| 2 | 200 | 189 | 11 | 5.5% |
| 4 | 400 | 334 | 66 | 16.5% |
| 8 | 800 | 515 | 285 | **35.6%** |

**WAL 모드 (timeout=0.05s)**

| 스레드 | 예상 | 성공 | 잠금에러 | 실패율 |
|--------|------|------|----------|--------|
| 1 | 100 | 100 | 0 | 0% |
| 4 | 400 | 347 | 53 | 13.3% |
| 8 | 800 | 614 | 186 | **23.3%** |

**WAL 모드 (timeout=5s — 대기 허용)**

| 스레드 | 예상 | 성공 | 잠금에러 | writes/s |
|--------|------|------|----------|----------|
| 1 | 100 | 100 | 0 | 273 |
| 8 | 800 | 800 | 0 | 325 |

교훈:
- DELETE 모드: 8스레드에서 **35.6% 데이터 유실** (파일 배타 잠금)
- WAL 모드: 읽기+쓰기는 동시 가능, 쓰기+쓰기는 여전히 직렬화
- 긴 timeout: 에러 없지만 writes/s가 스레드에 **비례하지 않음** (273 → 325, 1.2배)

### 4-2. SQLite vs PostgreSQL 동시 쓰기

> GIL=0, 스레드당 100건 INSERT, WAL/timeout=5s

| 스레드 | SQLite writes/s | PostgreSQL writes/s | PG/SQLite |
|--------|-----------------|---------------------|-----------|
| 1 | 260 | 487 | 1.9x |
| 2 | 298 | 773 | 2.6x |
| 4 | 226 | 1,543 | **6.8x** |
| 8 | 362 | 2,945 | **8.1x** |
| 16 | 425 | 4,794 | **11.3x** |

```
                writes/s (16 스레드)
    SQLite       ██                                         425
    PostgreSQL   ████████████████████████████████████████   4,794  (11.3x)
```

- **SQLite**: 1→16 스레드에서 260→425 (1.6배) — 내부 직렬화
- **PostgreSQL**: 487→4,794 (**9.8배**) — MVCC로 스레드에 비례하여 증가

### 4-3. 커넥션 풀 크기 실험

> 20개 동시 스레드, 스레드당 5회 쓰기, max_overflow=0

| pool_size | 시간 | writes/s | pool_size=1 대비 |
|-----------|------|----------|-----------------|
| 1 | 0.300s | 333 | 1x |
| 5 | 0.082s | 1,222 | 3.7x |
| 10 | 0.050s | 2,009 | 6.0x |
| 20 | 0.037s | 2,691 | **8.1x** |

교훈:
- **1→5로만 늘려도 3.7배 개선** (가장 효과가 큰 구간)
- 10→20은 개선폭 감소 (DB 서버 자체가 병목)
- 실무 가이드: `pool_size ≈ 예상 동시 요청 수 (5~20)`

---

## 5. 전체 종합

### 5-1. 동시성 방식 선택 가이드

| 상황 | 추천 방식 | 이유 |
|------|----------|------|
| C 확장 CPU-bound (Pillow, NumPy) | threading | GIL 유무 무관, 오버헤드 최소 |
| 순수 Python CPU-bound | frethread (GIL=0) | GIL=0에서만 진정한 병렬 |
| 순수 Python CPU-bound + GIL=1 | multiprocessing | GIL 우회 유일한 방법 |
| I/O-bound (네트워크, 파일) | asyncio / threading | await 양보로 동시성 확보 |
| DB 동시 쓰기 | PostgreSQL + 커넥션 풀 | MVCC로 진짜 병렬 쓰기 |

### 5-2. 핵심 숫자 요약

| 실험 | 비교 | 차이 |
|------|------|------|
| GIL=0 threading vs GIL=1 threading | 순수 Python fib(34)×4 | **3.6배** (1.13s vs 4.03s) |
| threading w=8 vs sync | 100장 blur | **5.4배** (4.1s vs 22.1s) |
| PostgreSQL vs SQLite | 16스레드 동시 쓰기 | **11.3배** (4,794 vs 425 w/s) |
| pool_size=20 vs pool_size=1 | 20스레드 동시 쓰기 | **8.1배** (2,691 vs 333 w/s) |

### 5-3. free-threaded Python의 가치와 한계

**가치가 명확한 경우:**
- 순수 Python CPU-bound 작업 (데이터 파싱, 연산, 변환)
- GIL=0에서 threading이 multiprocessing을 대체 가능 (오버헤드 훨씬 적음)
- DB 동시 접근이 늘어나므로 PostgreSQL + 커넥션 풀이 필수

**가치가 제한적인 경우:**
- C 확장 위주 작업 (Pillow, NumPy) — 이미 GIL을 릴리즈하므로 차이 적음
- I/O-bound 작업 — asyncio로 충분

**현재 한계 (2026년 2월 기준):**
- 일부 C 확장 패키지에 free-threaded 휠 미제공 (psycopg[binary] 등)
- multiprocessing의 fork()가 multi-threaded 프로세스에서 deadlock 경고
- 생태계 전반의 thread-safety 검증이 아직 진행 중

---

## 6. 벤치마크 스크립트 목록

| 스크립트 | 위치 | 실행 방법 |
|---------|------|----------|
| GIL 벤치마크 | src/scripts/bench_gil.py | `docker exec nogil-bench-compose uv run python src/scripts/bench_gil.py` |
| 기준선 측정 | src/scripts/bench_baseline.py | 동일 |
| async 실험 | src/scripts/bench_async.py | 동일 |
| 동시성 3종 | src/scripts/bench_concurrency.py | 동일 |
| 16조합 매트릭스 | src/scripts/bench_matrix.py | 동일 |
| 48조합 매트릭스 | src/scripts/bench_matrix_full.py | 동일 |
| SQLite 한계 | src/scripts/bench_db_sqlite_limits.py | 동일 |
| SQLite vs PG | src/scripts/bench_db_write.py | 동일 (PostgreSQL 필요) |
| 커넥션 풀 | src/scripts/bench_db_pool.py | 동일 (PostgreSQL 필요) |

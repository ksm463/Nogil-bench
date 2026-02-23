# Day 6 학습 가이드: DB 동시성의 본질

> 핵심 질문: "왜 SQLite는 동시 쓰기에 약하고, PostgreSQL은 강한가?"

---

## 1. 데이터베이스와 동시성 — 왜 중요한가

이 프로젝트는 free-threaded Python(GIL=0)에서 **진짜 병렬 스레드**를 실행한다.
Day 5까지는 이미지 처리(CPU-bound)의 병렬화를 다뤘지만,
실제 애플리케이션에서는 **스레드들이 동시에 DB에 접근**하는 상황이 반드시 발생한다.

```
GIL=1 시절:
  Thread A: DB 쓰기 ──────────────
  Thread B:          대기(GIL)     DB 쓰기 ──────
  → 사실상 순차 실행이라 DB 동시 접근 문제가 드러나지 않음

GIL=0 (free-threaded):
  Thread A: DB 쓰기 ──────────────
  Thread B: DB 쓰기 ──────────────  ← 동시에 접근!
  Thread C: DB 쓰기 ──────────────  ← 동시에 접근!
  → 진짜 병렬 → DB가 이걸 어떻게 처리하느냐가 성능을 결정
```

GIL이 숨겨주던 동시성 문제가 GIL=0에서 드러나는 것은
이미지 처리뿐만 아니라 **DB 접근에서도 동일하게 적용**된다.

---

## 2. SQLite의 동시성 모델

### 파일 기반 잠금 (File-level Locking)

SQLite는 **단일 파일**이 데이터베이스 전체다.
동시 접근은 OS의 파일 잠금(file lock)으로 제어한다.

```
SQLite 잠금 상태 전이:

  UNLOCKED → SHARED → RESERVED → PENDING → EXCLUSIVE
     ↑         ↑                              ↑
   아무도    읽기 가능                      쓰기 중
   안 씀    (여러 명 동시에)              (단 한 명만)
```

핵심 제약:
- **읽기(SHARED)**: 여러 스레드가 동시에 가능
- **쓰기(EXCLUSIVE)**: **단 한 스레드만** 가능. 나머지는 대기
- 쓰기 중에는 읽기도 차단됨 (PENDING 상태)

### `database is locked` 에러

```python
# 스레드 A가 쓰기 중 (EXCLUSIVE 잠금 보유)
session_a.add(record)
session_a.commit()  # EXCLUSIVE 잠금 획득

# 스레드 B가 동시에 쓰기 시도
session_b.add(record)
session_b.commit()  # → OperationalError: database is locked
```

SQLite는 기본적으로 5초(timeout) 동안 잠금 해제를 기다린다.
5초 내에 해제되지 않으면 `database is locked` 에러를 발생시킨다.

GIL=0에서 8개 스레드가 동시에 쓰기를 시도하면:
- 1개만 쓰기 성공
- 나머지 7개는 대기 → timeout 시 에러

### WAL (Write-Ahead Logging) 모드

```sql
PRAGMA journal_mode=WAL;
```

WAL 모드가 개선하는 것:
- **읽기 + 쓰기 동시 가능** (기본 모드에서는 쓰기 중 읽기 차단)
- 읽기는 WAL 파일의 스냅샷을 참조하므로 쓰기에 영향 받지 않음

WAL 모드가 개선하지 **않는** 것:
- **쓰기 + 쓰기 동시성**: 여전히 한 번에 한 스레드만 쓸 수 있음
- 쓰기는 여전히 EXCLUSIVE 잠금이 필요

```
WAL 모드 요약:
  읽기 + 읽기: ✅ 동시 가능 (WAL 없어도 가능)
  읽기 + 쓰기: ✅ 동시 가능 (WAL의 핵심 이점)
  쓰기 + 쓰기: ❌ 여전히 직렬화
```

### `check_same_thread=False`의 의미

```python
# 이 프로젝트에서 사용 중인 설정
engine = create_engine(
    "sqlite:///./nogil_bench.db",
    connect_args={"check_same_thread": False},
)
```

SQLite의 Python 바인딩(`sqlite3`)은 기본적으로
**커넥션을 생성한 스레드에서만 사용**하도록 강제한다.
`check_same_thread=False`는 이 검사를 끈다.

이것은 "스레드 안전하게 만드는 것"이 **아니다**.
단지 "다른 스레드에서 써도 에러를 안 던지겠다"일 뿐이다.
실제 동시 접근 시의 잠금 문제는 여전히 존재한다.

---

## 3. PostgreSQL의 동시성 모델 — MVCC

### MVCC (Multi-Version Concurrency Control)

PostgreSQL은 파일 잠금 대신 **MVCC**를 사용한다.
각 행(row)의 여러 버전을 동시에 유지하여, 읽기와 쓰기가 서로를 차단하지 않는다.

```
PostgreSQL MVCC 동작 원리:

  Transaction A (쓰기):
    UPDATE users SET name='Alice' WHERE id=1;
    → 기존 행을 수정하지 않고, 새 버전(v2)을 생성
    → v1은 아직 존재 (다른 트랜잭션이 참조 중일 수 있음)

  Transaction B (읽기, A 커밋 전):
    SELECT * FROM users WHERE id=1;
    → v1을 읽음 (A의 변경을 아직 못 봄)

  Transaction A: COMMIT;
    → 이후 새 트랜잭션은 v2를 읽음
```

핵심 차이:
- **SQLite**: 파일 전체에 잠금 → 한 명이 쓰면 다른 모든 사람 대기
- **PostgreSQL**: 행 단위 버전 관리 → 서로 다른 행은 동시 쓰기 가능

```
동시 쓰기 비교:

SQLite:
  Thread A: INSERT row 1 ────── (EXCLUSIVE lock on entire file)
  Thread B:                대기  INSERT row 2 ──────
  Thread C:                     대기              INSERT row 3 ──
  → 직렬 실행

PostgreSQL:
  Thread A: INSERT row 1 ──────
  Thread B: INSERT row 2 ──────
  Thread C: INSERT row 3 ──────
  → 진짜 병렬 실행 (서로 다른 행이므로 충돌 없음)
```

### 트랜잭션 격리 수준 (Isolation Levels)

PostgreSQL은 4가지 격리 수준을 제공한다:

| 격리 수준 | Dirty Read | Non-repeatable Read | Phantom Read | 성능 |
|-----------|-----------|-------------------|-------------|------|
| READ UNCOMMITTED | 가능 | 가능 | 가능 | 최고 |
| READ COMMITTED (기본) | 불가 | 가능 | 가능 | 좋음 |
| REPEATABLE READ | 불가 | 불가 | 가능 | 보통 |
| SERIALIZABLE | 불가 | 불가 | 불가 | 낮음 |

PostgreSQL의 기본값은 **READ COMMITTED**:
- 커밋된 데이터만 읽을 수 있음
- 같은 쿼리를 두 번 실행하면 결과가 다를 수 있음 (다른 트랜잭션이 커밋한 경우)
- 대부분의 웹 애플리케이션에 적합한 균형점

---

## 4. 커넥션 풀링 (Connection Pooling)

### 왜 커넥션 풀이 필요한가

DB 커넥션 생성 비용:
```
TCP 핸드셰이크:     ~1ms (로컬) / ~50ms (네트워크)
TLS 협상:           ~10ms (사용 시)
PostgreSQL 인증:    ~5ms
프로세스 포크:       ~10ms (PostgreSQL은 커넥션당 프로세스 생성)
──────────────────────────
총합:               ~25-75ms per connection
```

요청마다 새 커넥션을 열면 이 비용이 **매 요청마다** 반복된다.
커넥션 풀은 미리 커넥션을 열어두고 재사용한다.

### SQLAlchemy의 QueuePool

```python
engine = create_engine(
    "postgresql+psycopg://...",
    pool_size=5,        # 유휴 커넥션 수
    max_overflow=10,    # 추가 허용 수
    pool_pre_ping=True, # 커넥션 생존 확인
    pool_recycle=3600,  # 커넥션 최대 수명(초)
)
```

동작 흐름:
```
요청 도착 → 풀에서 커넥션 꺼냄 (checkout)
             ↓
          DB 작업 수행
             ↓
          커넥션을 풀에 반환 (checkin)
             ↓
        다음 요청이 재사용
```

### pool_size와 max_overflow

```
pool_size=5, max_overflow=10인 경우:

동시 요청 1~5개:  풀의 유휴 커넥션 사용 (빠름)
동시 요청 6~15개: overflow 커넥션 새로 생성 (약간 느림)
동시 요청 16개~:  대기 (pool_timeout까지) → 에러

                 ┌── pool_size ──┐┌── max_overflow ──┐
커넥션:          [1] [2] [3] [4] [5] [6] [7] ... [15]
                 └── 항상 유지 ──┘└── 필요 시 생성 ──┘
                                  └── 반환 후 즉시 폐기 ──┘
```

### pool_size 설정 가이드

```
pool_size가 너무 작으면 (예: 1):
  20개 동시 요청 → 1개만 처리, 19개 대기
  → 응답 시간 급증, timeout 에러 발생

pool_size가 너무 크면 (예: 100):
  PostgreSQL 커넥션당 ~10MB 메모리 사용
  100개 × 10MB = 1GB (대부분 유휴 상태로 낭비)
  PostgreSQL max_connections 기본값 = 100

적정값:
  pool_size ≈ 예상 동시 사용자 수
  max_overflow ≈ 피크 시 추가 여유분
  일반적으로 pool_size=5~20, max_overflow=10~20
```

### pool_pre_ping의 역할

```python
pool_pre_ping=True
```

풀에서 커넥션을 꺼낼 때 `SELECT 1`을 실행하여 커넥션이 살아있는지 확인한다.

왜 필요한가:
- DB 서버가 재시작되면 기존 커넥션이 끊어짐
- 풀은 이를 모르고 끊어진 커넥션을 반환
- `pool_pre_ping=True`가 없으면 → `connection reset by peer` 에러
- 있으면 → 자동으로 끊어진 커넥션을 폐기하고 새로 생성

비용: 매 checkout마다 `SELECT 1` 1회 (< 1ms) — 안정성 대비 매우 저렴

### pool_recycle의 역할

```python
pool_recycle=3600  # 1시간
```

커넥션을 최대 1시간만 사용하고 폐기한다.

왜 필요한가:
- PostgreSQL은 long-lived 커넥션에서 메모리 누수 가능성
- 일부 네트워크 장비(로드밸런서, 방화벽)가 idle 커넥션을 끊음
- MySQL은 `wait_timeout`(기본 8시간) 이후 서버 측에서 끊음

---

## 5. free-threaded Python에서의 DB 접근 패턴

### 현재 프로젝트의 패턴

```python
# 패턴 1: FastAPI 요청 핸들러 (요청 스코프 세션)
@router.post("/api/benchmarks/run")
def run_benchmark(
    session: Session = Depends(get_session),  # 요청마다 새 세션
):
    result = BenchmarkResult(...)
    session.add(result)
    session.commit()
    # → 요청 끝나면 세션 자동 반환

# 패턴 2: BackgroundTasks (독립 세션)
def process_job(job_id: int):
    with Session(engine) as session:  # 자체 세션 생성
        job = session.get(Job, job_id)
        for image in images:
            # 처리 ...
            job.processed_count += 1
            session.commit()  # 중간 커밋 (진행률 업데이트)
```

### GIL=0에서 주의할 점

```
시나리오: 2개의 벤치마크 API 동시 호출

GIL=1:
  Request A: session.commit() ──────────────────
  Request B:                    대기(GIL)         session.commit()
  → SQLite도 문제없음 (GIL이 직렬화해줌)

GIL=0:
  Request A: session.commit() ──────────────────
  Request B: session.commit() ──────────────────  ← 동시!
  → SQLite: database is locked (or 직렬화 지연)
  → PostgreSQL: 둘 다 성공 (MVCC)
```

### Session과 Connection의 관계

```
Session ──uses──→ Connection ──from──→ Pool ──manages──→ DB

Session:     ORM 작업 단위 (add, query, commit)
Connection:  실제 DB 연결 (TCP 소켓)
Pool:        Connection을 재사용하는 저장소
DB:          PostgreSQL 서버 (프로세스 모델)
```

한 Session은 한 Connection을 사용한다.
Session이 닫히면 Connection이 풀에 반환된다.
풀이 없으면 Session이 닫힐 때 Connection도 폐기된다.

---

## 6. 실험으로 확인할 것들

### 실험 1: SQLite 동시 쓰기 한계

```
질문: SQLite에 8개 스레드가 동시에 쓰면 어떻게 되는가?
예상: database is locked 에러 또는 심각한 직렬화 지연
확인: bench_db_sqlite_limits.py 실행
```

### 실험 2: SQLite vs PostgreSQL 동시 쓰기 비교

```
질문: 같은 워크로드에서 SQLite와 PostgreSQL의 처리량 차이는?
예상: PostgreSQL이 스레드 수에 비례해 writes/sec 증가
확인: bench_db_write.py 실행
```

### 실험 3: 커넥션 풀 크기의 영향

```
질문: pool_size가 동시 요청 처리에 어떤 영향을 미치는가?
예상: pool_size < 동시 스레드 수 → 병목, pool_size ≈ 스레드 수 → 최적
확인: bench_db_pool.py 실행
```

### 실험 4: 48조합 벤치마크 + DB 저장

```
질문: 이미지 수를 10/50/100으로 늘리면 스케일링 패턴이 어떻게 변하는가?
예상: 이미지 수가 많을수록 병렬화 이득이 커짐 (오버헤드 비율 감소)
확인: bench_matrix_full.py 실행
```

---

## 7. 핵심 용어 정리

| 용어 | 설명 |
|------|------|
| **MVCC** | Multi-Version Concurrency Control. 행의 여러 버전을 유지하여 읽기/쓰기 동시 가능 |
| **WAL** | Write-Ahead Logging. 변경 사항을 별도 로그 파일에 먼저 기록. SQLite의 동시 읽기/쓰기 지원 |
| **커넥션 풀** | DB 커넥션을 미리 생성해두고 재사용하는 패턴. 커넥션 생성 오버헤드 제거 |
| **pool_size** | 풀에 유지할 유휴 커넥션 수 |
| **max_overflow** | pool_size 초과 시 추가 생성 가능한 커넥션 수 |
| **pool_pre_ping** | 커넥션 반환 전 생존 확인 (SELECT 1) |
| **pool_recycle** | 커넥션 최대 수명. 오래된 커넥션 자동 교체 |
| **Isolation Level** | 트랜잭션 간 데이터 가시성 수준 (READ COMMITTED 등) |
| **EXCLUSIVE lock** | SQLite의 파일 전체 쓰기 잠금. 한 번에 하나의 writer만 허용 |
| **Row-level lock** | PostgreSQL의 행 단위 잠금. 서로 다른 행은 동시 쓰기 가능 |

---

## 8. 참고: SQLite가 적합한 경우

SQLite가 나쁜 DB라는 뜻이 **아니다**. 사용 사례에 따라 최적의 선택이다:

| 상황 | SQLite | PostgreSQL |
|------|--------|-----------|
| 단일 사용자 앱 (모바일, 데스크톱) | ✅ 최적 | 과잉 |
| 읽기 위주 웹 서비스 | ✅ 충분 | 불필요 |
| 동시 쓰기가 빈번한 웹 서비스 | ❌ 병목 | ✅ 최적 |
| free-threaded 병렬 처리 | ❌ 직렬화 | ✅ 필수 |
| 임베디드 / 설정 저장 | ✅ 최적 | 과잉 |
| 프로토타이핑 / 테스트 | ✅ 빠른 시작 | 셋업 필요 |

이 프로젝트에서 Day 1~5까지 SQLite를 쓴 것은 올바른 선택이었다.
빠른 프로토타이핑에 SQLite는 이상적이다.
Day 6에서 PostgreSQL로 전환하는 것은 **동시 쓰기 워크로드**가 생겼기 때문이다.

# Day 7 학습 정리

> Free-threaded Python(3.14t, GIL=0) 프로젝트 7일간의 핵심 학습 내용

---

## 1. GIL의 정체와 free-threaded Python

**GIL(Global Interpreter Lock)이란:**
- CPython이 한 번에 하나의 스레드만 Python 바이트코드를 실행하도록 강제하는 잠금
- 멀티스레드를 써도 CPU-bound 작업이 병렬로 실행되지 않는 근본 원인

**Day 1 실험에서 확인한 것:**

```
fib(34) × 4회, 4스레드:
  GIL=1 → 4.03s (오히려 느려짐, 0.88x)
  GIL=0 → 1.13s (3.17x 빨라짐)
```

GIL=1에서 스레드를 늘리면 **역효과**가 난다. GIL 경합 + 컨텍스트 스위칭 비용 때문이다. GIL=0에서는 4스레드가 4개 코어를 실제로 사용하여 거의 선형에 가까운 속도 향상을 얻는다.

---

## 2. 동시성 4가지 모델의 차이

| 모델 | 원리 | 장점 | 단점 |
|------|------|------|------|
| **sync** | 순차 실행 | 단순, 디버깅 쉬움 | 병렬 없음 |
| **threading** | OS 스레드 | 오버헤드 적음, 메모리 공유 | GIL=1이면 CPU-bound에서 무용 |
| **multiprocessing** | 별도 프로세스 | GIL 무관 병렬 | 프로세스 생성 + pickle 직렬화 오버헤드 |
| **frethread** | OS 스레드 + GIL=0 | 진짜 병렬 + 낮은 오버헤드 | Lock 필수, 생태계 미성숙 |

**100장 이미지 blur, 워커 8개 결과:**

```
sync        ████████████████████████████████████████  22.1s
threading   ███████                                    4.1s (5.4x)
frethread   ████████                                   4.2s (5.3x)
mp          █████████████████████                     11.7s (1.9x)
```

multiprocessing이 threading보다 느린 이유는 이미지를 프로세스 간에 넘길 때 pickle 직렬화가 필요하기 때문이다.

---

## 3. C 확장과 GIL 릴리즈

**핵심 발견:** threading과 frethread의 성능이 거의 동일했다.

이유는 Pillow가 C 확장이기 때문이다. C 확장 라이브러리는 CPU 연산 중 `Py_BEGIN_ALLOW_THREADS` 매크로로 GIL을 자발적으로 해제한다. 그래서 GIL=1에서도 threading이 잘 작동한다.

```
순수 Python (fib):
  GIL=1 threading → 2.50s (sync보다 느림)
  GIL=0 threading → 0.71s (3.1x 빨라짐)

C 확장 (Pillow blur):
  GIL=1 threading → 0.79s (빠름!)
  GIL=0 threading → 0.80s (차이 없음)
```

**결론:** free-threaded Python의 가치는 **순수 Python** CPU-bound 작업에서 나타난다. NumPy, Pillow 같은 C 확장 위주라면 기존 threading으로 충분하다.

---

## 4. asyncio의 한계

```
10장 blur, GIL=0:
  async (pure)       → 2.276s (sync와 동일)
  executor (4 workers) → 0.763s (3.3x)
```

`async/await`는 **I/O 대기 중에 양보**하는 구조다. CPU-bound 작업에서는 양보할 시점이 없어서 sync와 차이가 없다. `run_in_executor`로 스레드풀에 위임하면 빨라지지만, 그건 결국 threading이다.

**정리:** asyncio는 네트워크/파일 I/O에 적합하고, CPU-bound에는 threading이나 multiprocessing을 써야 한다.

---

## 5. DB 동시성 — SQLite vs PostgreSQL

### SQLite의 근본적 한계

SQLite는 파일 기반 DB로, 쓰기 시 파일 전체를 잠근다.

```
8스레드 동시 INSERT (DELETE 모드, timeout=0.05s):
  → 800건 중 515건만 성공, 285건 잠금 에러 (35.6% 실패)
```

WAL 모드로 바꾸면 읽기+쓰기는 동시에 되지만, 쓰기+쓰기는 여전히 직렬화된다.

### PostgreSQL의 MVCC

PostgreSQL은 MVCC(Multi-Version Concurrency Control)로 각 트랜잭션이 데이터의 스냅샷을 보면서 동시에 쓰기가 가능하다.

```
16스레드 동시 쓰기:
  SQLite     →    425 writes/s
  PostgreSQL →  4,794 writes/s (11.3배)
```

SQLite는 스레드를 늘려도 처리량이 정체되지만, PostgreSQL은 스레드에 비례하여 증가한다. free-threaded Python에서 동시 DB 접근이 늘어나므로, **프로덕션에서는 PostgreSQL + 커넥션 풀이 사실상 필수**다.

---

## 6. 커넥션 풀의 효과

```
20개 동시 스레드, PostgreSQL:
  pool_size=1  → 333 writes/s (20개 스레드가 1개 커넥션을 돌려씀)
  pool_size=5  → 1,222 writes/s (3.7배 — 가장 효과 큰 구간)
  pool_size=20 → 2,691 writes/s (8.1배)
```

`pool_size=1→5`로만 늘려도 3.7배 개선된다. 이후로는 DB 서버 자체가 병목이 되어 개선폭이 줄어든다. 실무에서는 `pool_size ≈ 예상 동시 요청 수 (5~20)` 정도가 적절하다.

---

## 7. Thread-Safety — GIL이 숨겨주던 버그

**이것이 free-threaded Python의 가장 중요한 교훈이다.**

GIL=1에서는 한 번에 하나의 스레드만 실행되므로, 공유 자원에 대한 race condition이 드러나지 않는다. 하지만 이것은 **코드가 올바른 게 아니라 우연히 안전한 것**이다.

```python
# 이 코드는 GIL=1에서 "잘 돌아가지만" 틀린 코드다
counter = {"value": 0}

def worker():
    for _ in range(100_000):
        current = counter["value"]      # read
        counter["value"] = current + 1   # write
        # ↑ read와 write 사이에 다른 스레드가 끼어들 수 있음
```

```
GIL=0, 8스레드 × 100,000 = 기댓값 800,000:
  Lock 없음 → ~150,000 (81% 손실!)
  Lock 사용 → 800,000 (정확)
```

**해결:**

```python
lock = threading.Lock()

def worker():
    for _ in range(100_000):
        with lock:  # critical section 보호
            current = counter["value"]
            counter["value"] = current + 1
```

Check-then-act 패턴도 동일한 문제가 있다. `if len(list) < limit`을 확인한 후 `list.append()`하는 사이에 다른 스레드가 끼어들면 limit을 초과한다. check와 act를 Lock으로 하나의 원자적 블록으로 만들어야 한다.

---

## 8. 실무 선택 가이드

```
어떤 동시성 모델을 쓸 것인가?

  ┌─ CPU-bound?
  │   ├─ C 확장 (Pillow, NumPy) → threading (GIL 무관)
  │   ├─ 순수 Python + GIL=0   → threading (frethread)
  │   └─ 순수 Python + GIL=1   → multiprocessing
  │
  └─ I/O-bound?
      └─ asyncio 또는 threading

  DB 동시 쓰기가 많다면?
  └─ PostgreSQL + 커넥션 풀 (pool_size=5~20)

  공유 상태를 변경한다면?
  └─ threading.Lock 필수 (GIL에 의존하지 말 것)
```

---

## 9. free-threaded Python의 현재 위치 (2026년 2월)

**쓸 만한 경우:**
- 순수 Python CPU-bound에서 multiprocessing 대신 threading을 쓸 수 있게 됨 (프로세스 오버헤드 제거)

**아직 이른 경우:**
- `psycopg[binary]` 등 일부 C 확장에 free-threaded 휠이 없음
- `multiprocessing.fork()`가 멀티스레드 프로세스에서 deadlock 경고
- 기존 코드의 thread-safety가 검증되지 않은 상태에서 GIL=0 전환은 위험

**핵심 메시지:** GIL 제거는 "공짜 병렬화"가 아니다. 진짜 병렬이 되는 만큼 동시성 버그도 진짜가 된다. Lock, Queue, thread-local 등 올바른 동기화 도구를 사용하는 것이 전제 조건이다.

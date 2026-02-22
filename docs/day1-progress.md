# Day 1 진행 기록

> 날짜: 2026-02-20 (목)
> 단계: 프로젝트 셋업 — 환경 구성 + FastAPI 뼈대 + GIL 벤치마크

---

## 1. 프로젝트 계획 검토

### 잘된 점
- 핵심 주제(CPU-bound 4가지 동시성 비교)가 전체 프로젝트를 관통하는 명확한 축
- Day 1→7 점진적 빌드업 구조가 자연스러움
- `daily-learning-guide.md`의 "동작하는 API" / "이해하게 되는 것" 구분이 효과적

### 주의할 점
- **Day 3, 5 일정이 빠듯함** — 필요시 Day 5 배치 API를 Day 4로 앞당기거나 유연하게 운영
- **free-threaded 생태계 호환성** — Pillow, SQLAlchemy 등 C 확장 패키지의 `GIL=0` 동작 검증 필요
- **테스트 전략** — Day 4에 몰아서 작성하기보다 Day 2-3부터 간단한 동작 확인 테스트 병행 권장
- `processor/` runner들의 공통 인터페이스(BaseRunner/Protocol) 정의하면 코드 중복 감소

---

## 2. Python 3.14 Free-threaded Docker 이미지 조사

### Python 3.14 현황
- **3.14.0** 정식 릴리스: 2025-10-07
- **3.14.3** 최신 버그픽스: 2026-02-03
- free-threading: PEP 779로 **experimental → officially supported** 승격

### Docker Hub 공식 이미지 (`python:`) 조사 결과

| 태그 | 존재 여부 |
|------|-----------|
| `python:3.14` | O |
| `python:3.14-slim` | O |
| `python:3.14-slim-trixie` | O |
| `python:3.14-slim-bookworm` | O |
| `python:3.14-alpine` | O |
| `python:3.14t` | **X (없음)** |
| `python:3.14-free-threading` | **X (없음)** |

> **결론**: 공식 Docker Hub에 free-threaded 전용 태그는 아직 없음

### 대안 경로 3가지

**방법 1 — 공식 이미지 + `Py_GIL_DISABLED` 확인 (우선 시도)**
```bash
docker run --rm python:3.14-slim python -c \
  "import sysconfig; print(sysconfig.get_config_var('Py_GIL_DISABLED'))"
# 1이면 → PYTHON_GIL=0 환경변수로 GIL 비활성화 가능
# 0 또는 None이면 → 소스 빌드 필요
```

**방법 2 — PyPA manylinux 이미지**
- `quay.io/pypa/manylinux_2_28_x86_64` 에 `python3.14t`가 `/opt/python/`에 포함
- 단, wheel 빌드용 이미지라 앱 서버 용도로는 무거움

**방법 3 — Dockerfile에서 소스 빌드**
```dockerfile
FROM python:3.14-slim
RUN apt-get update && apt-get install -y build-essential ...
# CPython 소스에서 --disable-gil로 재빌드
```

---

## 3. Docker 환경 구성

### 설치 완료
```
docker-ce          29.2.1
docker-ce-cli      29.2.1
containerd.io      2.2.1
docker-buildx      0.31.1
docker-compose     5.0.2
```

### 권한 문제 해결
```bash
# 문제: docker 명령 시 permission denied (docker.sock 접근 불가)
# 원인: ksm 사용자가 docker 그룹에 미포함
# 해결:
sudo usermod -aG docker ksm
# 이후 셸(터미널) 재시작 필요
```

### 동작 확인
```
$ docker ps -a   # 정상 동작
$ docker rm elastic_shockley   # hello-world 테스트 컨테이너 정리 완료
```

---

## 4. 이미지 조사 결과: `Py_GIL_DISABLED` 확인

```
$ docker run --rm python:3.14-slim python -c \
    "import sysconfig; print(sysconfig.get_config_var('Py_GIL_DISABLED'))"
0
```

- `python:3.14-slim` → `Py_GIL_DISABLED=0` (free-threaded 아님)
- `python:3.14t-slim` → 태그 존재하지 않음
- `quay.io/pypa/manylinux_2_28_x86_64` → `cp314-cp314t` 존재, `Py_GIL_DISABLED=1` 확인

> **결정**: 방법 3 (소스 빌드) 채택 — `python:3.14-slim` 위에서 `--disable-gil`로 CPython 재컴파일

---

## 5. Docker 이미지 빌드 + 컨테이너 실행

### 구성 파일

| 파일 | 역할 |
|------|------|
| `Dockerfile` | builder(CPython 소스 빌드) → base(런타임) → test → production |
| `build_docker.sh` | `docker build --progress=plain` (캐시 활용, `--no-cache` 제거) |
| `run_docker.sh` | 볼륨 마운트 + Named Volume(.venv 보존) + `PYTHON_GIL=0` |

### Dockerfile 핵심 구조

```
builder: python:3.14-slim + build-essential → ./configure --disable-gil → /opt/python-ft
base:    python:3.14-slim + /opt/python-ft 복사 + uv + uv sync
```

### 빌드 검증 (이미지 내부)

```
Python 3.14.3 free-threading build (main, Feb 20 2026, 10:20:18) [GCC 14.2.0]
GIL disabled: True
```

### .venv 보존 전략 (vs-model-test 패턴 차용)

```bash
# run_docker.sh
-v ${project_path}:/app \              # 코드 마운트 (덮어씀)
-v nogil-bench-venv:/app/.venv \       # Named Volume → .venv 보존
```

- Dockerfile에서 `uv sync` → .venv 생성 (이미지에 포함)
- Named Volume이 .venv를 보존 → 볼륨 마운트로 덮어씌워지지 않음

---

## 6. 의존성 설정 (`pyproject.toml`)

### free-threaded Python 3.14 호환성 조사 결과

| 원래 계획 | 문제 | 대체 패키지 |
|-----------|------|-------------|
| passlib | Python 3.14에서 동작 불가 (`crypt` 모듈 제거됨) | **pwdlib[bcrypt]** |
| python-jose | 유지보수 중단 | **PyJWT** |
| httptools (uvicorn[standard]) | cp314t 미지원 | **h11** (uvicorn 기본 파서) |

### 설치된 패키지 (24개)

```
fastapi==0.129.0, uvicorn==0.41.0, sqlmodel==0.0.34
pillow==12.1.1, pyjwt==2.11.0, pwdlib==0.3.0, bcrypt==5.0.0
loguru==0.7.3, psutil==7.2.2, pydantic-settings==2.13.1
+ 의존성 패키지들
```

---

## 7. FastAPI 앱 뼈대

### 생성된 파일

```
src/
├── main.py              # FastAPI 앱, /health 엔드포인트
├── core/
│   ├── config.py        # pydantic-settings (환경변수 + .env)
│   └── lifespan.py      # startup/shutdown 생명주기
└── utility/
    └── logger.py        # Loguru 로깅 설정
```

### 헬스체크 엔드포인트 동작 확인

```json
GET /health
{
    "status": "ok",
    "python_version": "3.14.3",
    "free_threaded": true,
    "gil_enabled": false
}
```

- Swagger UI (`http://localhost:8000/docs`) 접속 확인 완료

---

## 8. GIL=1 vs GIL=0 벤치마크

### 실험 스크립트: `scripts/bench_gil.py`

- CPU-bound 작업: 재귀 피보나치 `fib(34)` × 4회
- 순차 실행 vs 4스레드 실행 비교

### 결과

| | Sequential | Threaded (4) | Speedup |
|---|---|---|---|
| **GIL=0** (비활성화) | 3.58s | 1.13s | **3.17x** |
| **GIL=1** (활성화) | 3.55s | 4.03s | **0.88x** |

- **GIL=0**: 4스레드로 3.17배 빨라짐 — 진짜 병렬 실행
- **GIL=1**: 스레드를 써도 오히려 느려짐 — GIL 경합 + 컨텍스트 스위칭 오버헤드

---

## 9. Day 1 완료 체크리스트

- [x] `python:3.14-slim`에서 `Py_GIL_DISABLED` 값 확인
- [x] CPython 소스 빌드 방식으로 Dockerfile 작성
- [x] `build_docker.sh` / `run_docker.sh` 작성
- [x] `pyproject.toml` 의존성 설정 (free-threaded 호환성 검증 포함)
- [x] FastAPI 앱 뼈대 (`main.py`, `core/config.py`, `core/lifespan.py`)
- [x] 헬스체크 엔드포인트 (`GET /health`)
- [x] Loguru 로깅 설정 (`utility/logger.py`)
- [x] GIL=1 vs GIL=0 벤치마크 스크립트 + 결과

---

## 참고 링크

- [PEP 745 – Python 3.14 Release Schedule](https://peps.python.org/pep-0745/)
- [PEP 779 – Free-threading officially supported in 3.14](https://peps.python.org/pep-0779/)
- [Python free-threading guide](https://docs.python.org/3/howto/free-threading-python.html)
- [py-free-threading.github.io](https://py-free-threading.github.io/)
- [Docker Hub - Python Official Image](https://hub.docker.com/_/python)
- [PyPA manylinux (GitHub)](https://github.com/pypa/manylinux)

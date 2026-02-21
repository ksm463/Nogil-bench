# Nogil-bench 프로젝트 가이드

## 실행 환경

- 모든 코드는 **Docker 컨테이너 내부**에서 실행된다.
- 컨테이너 이름: `nogil-bench`
- 호스트의 코드가 `/app`에 볼륨 마운트되어 있다.
- 컨테이너에는 `ps`, `pkill` 등 일반 유틸리티가 없다 (slim 이미지).

## 명령어 실행 방법

```bash
# 컨테이너 내부에서 명령 실행
docker exec nogil-bench <command>

# 패키지 설치/동기화
docker exec nogil-bench uv sync

# 서버 실행 (컨테이너 내부 /app/src에서)
docker exec nogil-bench bash -c "cd /app/src && uv run main.py"

# 스크립트 실행
docker exec nogil-bench uv run python src/scripts/<script>.py

# 테스트 실행
docker exec nogil-bench uv run pytest
```

- **호스트에서 직접 `uv run`을 실행하지 않는다** — free-threaded Python 3.14t는 컨테이너 안에만 있다.
- API 테스트(curl)는 호스트에서 `http://localhost:8000`으로 접근 가능하다 (포트 매핑 8000:8000).

## 프로젝트 구조

- 소스 코드: `src/` (PYTHONPATH 루트는 `src/`)
- 테스트: `tests/`
- 문서: `docs/`
- 스크립트: `src/scripts/`

## 기술 스택

- Python 3.14t (free-threaded, GIL 비활성화)
- FastAPI + Uvicorn
- SQLModel (SQLite → 추후 PostgreSQL)
- 패키지 관리: uv

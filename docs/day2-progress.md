# Day 2 진행 기록

> 날짜: 2026-02-20 (목)
> 단계: 이미지 CRUD + 파일 업로드 + 동시성 기준선 측정

---

## 1. SQLModel DB 모델 정의

### 생성된 파일

```
src/model/
├── database.py    # 엔진, 세션, 테이블 생성
├── user.py        # User 테이블 (Day 3 인증 준비)
└── image.py       # ImageRecord 테이블
```

### 테이블 구조

**user**

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | INTEGER | PK, 자동 증가 |
| email | VARCHAR | unique, index |
| hashed_password | VARCHAR | |
| created_at | DATETIME | |

**imagerecord**

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | INTEGER | PK, 자동 증가 |
| filename | VARCHAR | 원본 파일명 |
| original_path | VARCHAR | 업로드 경로 |
| output_path | VARCHAR | 처리 결과 경로 (nullable) |
| operation | VARCHAR | 적용된 처리 (nullable) |
| status | VARCHAR | uploaded/processing/completed/failed |
| user_id | INTEGER | FK → user.id (nullable, Day 3에서 활성화) |
| created_at | DATETIME | |

### 설계 결정

- `model` 폴더명 사용 — 웹 백엔드 표준 컨벤션 (Django, FastAPI 공통). AI 모델과 혼동 시 AI 쪽을 `engine/`, `inference/` 등으로 분리하는 것이 일반적
- `datetime.now(UTC)` 사용 — Python 3.12+에서 `datetime.utcnow()` deprecated
- SQLite `check_same_thread=False` — FastAPI의 멀티스레드 요청 처리를 위해 필요

---

## 2. 이미지 처리 함수 (processor/operations.py)

### 구현된 함수 6개

| 함수 | 파라미터 | 설명 |
|---|---|---|
| `resize(image, width, height)` | 크기 | LANCZOS 리사이즈 |
| `blur(image, radius)` | 반경 | 가우시안 블러 |
| `sharpen(image)` | - | 샤프닝 필터 |
| `grayscale(image)` | - | 흑백 변환 (RGB 유지) |
| `rotate(image, degrees)` | 각도 | 회전 (expand=True) |
| `watermark(image, text)` | 텍스트 | 우하단 워터마크 |

- 모든 함수가 `Image → Image` 순수 함수
- 이후 sync/thread/multiprocessing/free-threaded 러너에서 그대로 사용

### 실제 이미지 테스트

테스트용 이미지 4장 (`tests/fixtures/`):

| 파일 | 사이즈 | 용도 |
|---|---|---|
| test_cat.png | 2816x1536 | 질감(털) 처리 확인 |
| test_landscape.png | 2816x1536 | 넓은 색상 범위, 해상도 변경 |
| test_portrait.png | 1696x2528 | 회전 등 |
| test_text.png | 1408x768 | 워터마크 겹침 확인 |

`src/scripts/test_operations.py`로 4장 × 6개 처리 = 24개 결과 파일 생성 확인

---

## 3. REST API 구현 (서비스 레이어 패턴)

### 레이어 구조

```
router/image_router.py   → HTTP 요청/응답만 담당
service/image_service.py → 비즈니스 로직 (파일 저장, DB 조작, 이미지 처리)
```

### 엔드포인트 6개

| 메서드 | 경로 | 동작 | 테스트 결과 |
|---|---|---|---|
| POST | `/api/images/upload` | 이미지 업로드 | id=1 반환 |
| GET | `/api/images/` | 목록 조회 | 1건 반환 |
| GET | `/api/images/{id}` | 상세 조회 | 정상 |
| POST | `/api/images/{id}/process` | 처리 요청 | blur → status: completed |
| GET | `/api/images/{id}/download` | 결과 다운로드 | 207KB JPEG |
| DELETE | `/api/images/{id}` | 삭제 | 파일 + DB 삭제 |

### 추가된 의존성

- `python-multipart>=0.0.22` — FastAPI `UploadFile`에 필수 (Pure Python, GIL 무관)

---

## 4. 동시성 기준선 측정

### 생성된 파일

```
src/
├── utility/
│   └── timer.py           # 시간 측정 컨텍스트 매니저
└── processor/
    └── sync_runner.py     # 동기 순차 처리 러너
```

### Baseline 결과 (10장, 순차 처리)

| 처리 | 총 시간 | 이미지당 |
|---|---|---|
| **blur** | 2.435s | 243.5ms |
| rotate | 2.214s | 221.4ms |
| sharpen | 1.561s | 156.1ms |
| resize | 1.305s | 130.5ms |
| grayscale | 1.090s | 109.0ms |
| watermark | 0.976s | 97.6ms |

- **blur가 가장 CPU를 많이 사용** → Day 5 벤치마크의 대표 작업으로 채택
- 이 수치가 threading/multiprocessing/free-threaded 비교의 기준선

---

## 5. Day 2 완료 체크리스트

- [x] SQLModel DB 모델 정의 (`model/database.py`, `model/user.py`, `model/image.py`)
- [x] 이미지 처리 함수 작성 (`processor/operations.py`) — 6개 함수
- [x] 실제 이미지 테스트 (`scripts/test_operations.py`) — 4장 × 6개 = 24개 결과
- [x] REST API 구현 (`router/image_router.py` + `service/image_service.py`) — 6개 엔드포인트
- [x] 서비스 레이어 패턴 적용 — 라우터는 HTTP만, 로직은 서비스에
- [x] 전체 플로우 테스트 — 업로드 → 처리 → 다운로드 → 삭제
- [x] 처리 시간 측정 유틸리티 (`utility/timer.py`)
- [x] 동기 순차 처리 러너 (`processor/sync_runner.py`)
- [x] 기준선 성능 기록 — 10장 blur 2.435s

---

## 6. 현재 프로젝트 구조

```
src/
├── main.py
├── core/
│   ├── config.py
│   └── lifespan.py
├── model/
│   ├── database.py
│   ├── user.py
│   └── image.py
├── processor/
│   ├── operations.py
│   └── sync_runner.py
├── router/
│   └── image_router.py
├── service/
│   └── image_service.py
├── utility/
│   ├── logger.py
│   └── timer.py
└── scripts/
    ├── bench_gil.py
    ├── bench_baseline.py
    └── test_operations.py
```

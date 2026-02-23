"""배치 처리 작업 API 테스트.

POST /api/jobs/batch        — 배치 작업 생성 (202)
GET  /api/jobs/              — 작업 목록
GET  /api/jobs/{id}          — 작업 상태
GET  /api/jobs/{id}/result   — 완료된 결과

Note: TestClient에서 BackgroundTasks는 응답 반환 전에 동기적으로 실행된다.
따라서 202 응답 직후 작업이 이미 completed 상태임.
"""

import io
from pathlib import Path

from PIL import Image

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _upload_image(client, auth_headers, filename="test_cat.png"):
    """테스트용 이미지를 업로드하고 image_id를 반환한다."""
    img_path = FIXTURES_DIR / filename
    with open(img_path, "rb") as f:
        resp = client.post(
            "/api/images/upload",
            files={"file": (filename, f, "image/png")},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    return resp.json()["id"]


class TestCreateBatchJob:
    def test_create_batch(self, client, auth_headers):
        img_id = _upload_image(client, auth_headers)
        resp = client.post(
            "/api/jobs/batch",
            json={"image_ids": [img_id], "operation": "blur"},
            headers=auth_headers,
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] in ("queued", "processing", "completed")
        assert data["image_count"] == 1
        assert data["operation"] == "blur"

    def test_batch_completes(self, client, auth_headers):
        """TestClient에서 BackgroundTasks가 동기 실행되므로 즉시 완료."""
        img_id = _upload_image(client, auth_headers)
        resp = client.post(
            "/api/jobs/batch",
            json={"image_ids": [img_id], "operation": "blur"},
            headers=auth_headers,
        )
        job_id = resp.json()["id"]

        status_resp = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
        assert status_resp.json()["status"] == "completed"
        assert status_resp.json()["processed_count"] == 1
        assert status_resp.json()["duration"] is not None

    def test_batch_multiple_images(self, client, auth_headers):
        ids = [
            _upload_image(client, auth_headers, "test_cat.png"),
            _upload_image(client, auth_headers, "test_landscape.png"),
        ]
        resp = client.post(
            "/api/jobs/batch",
            json={"image_ids": ids, "operation": "grayscale"},
            headers=auth_headers,
        )
        assert resp.status_code == 202
        job_id = resp.json()["id"]

        status_resp = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
        assert status_resp.json()["processed_count"] == 2

    def test_batch_invalid_image(self, client, auth_headers):
        resp = client.post(
            "/api/jobs/batch",
            json={"image_ids": [9999], "operation": "blur"},
            headers=auth_headers,
        )
        assert resp.status_code == 404
        assert resp.json()["error_code"] == "IMAGE_NOT_FOUND"

    def test_batch_other_user_image(self, client, auth_headers, second_user_headers):
        img_id = _upload_image(client, auth_headers)
        resp = client.post(
            "/api/jobs/batch",
            json={"image_ids": [img_id], "operation": "blur"},
            headers=second_user_headers,
        )
        assert resp.status_code == 403

    def test_batch_invalid_method(self, client, auth_headers):
        img_id = _upload_image(client, auth_headers)
        resp = client.post(
            "/api/jobs/batch",
            json={"image_ids": [img_id], "operation": "blur", "method": "invalid"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "INVALID_METHOD"

    def test_batch_invalid_operation(self, client, auth_headers):
        img_id = _upload_image(client, auth_headers)
        resp = client.post(
            "/api/jobs/batch",
            json={"image_ids": [img_id], "operation": "invalid"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "INVALID_OPERATION"

    def test_batch_without_auth(self, client):
        resp = client.post(
            "/api/jobs/batch",
            json={"image_ids": [1], "operation": "blur"},
        )
        assert resp.status_code == 401


class TestListJobs:
    def test_list_empty(self, client, auth_headers):
        resp = client.get("/api/jobs/", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_after_batch(self, client, auth_headers):
        img_id = _upload_image(client, auth_headers)
        client.post(
            "/api/jobs/batch",
            json={"image_ids": [img_id], "operation": "blur"},
            headers=auth_headers,
        )
        resp = client.get("/api/jobs/", headers=auth_headers)
        assert len(resp.json()) == 1

    def test_list_only_own(self, client, auth_headers, second_user_headers):
        img_id = _upload_image(client, auth_headers)
        client.post(
            "/api/jobs/batch",
            json={"image_ids": [img_id], "operation": "blur"},
            headers=auth_headers,
        )
        resp = client.get("/api/jobs/", headers=second_user_headers)
        assert len(resp.json()) == 0


class TestGetJob:
    def test_get_status(self, client, auth_headers):
        img_id = _upload_image(client, auth_headers)
        run_resp = client.post(
            "/api/jobs/batch",
            json={"image_ids": [img_id], "operation": "blur"},
            headers=auth_headers,
        )
        job_id = run_resp.json()["id"]
        resp = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == job_id

    def test_get_not_found(self, client, auth_headers):
        resp = client.get("/api/jobs/9999", headers=auth_headers)
        assert resp.status_code == 404
        assert resp.json()["error_code"] == "JOB_NOT_FOUND"

    def test_get_other_user(self, client, auth_headers, second_user_headers):
        img_id = _upload_image(client, auth_headers)
        run_resp = client.post(
            "/api/jobs/batch",
            json={"image_ids": [img_id], "operation": "blur"},
            headers=auth_headers,
        )
        job_id = run_resp.json()["id"]
        resp = client.get(f"/api/jobs/{job_id}", headers=second_user_headers)
        assert resp.status_code == 404


class TestGetJobResult:
    def test_get_result(self, client, auth_headers):
        img_id = _upload_image(client, auth_headers)
        run_resp = client.post(
            "/api/jobs/batch",
            json={"image_ids": [img_id], "operation": "blur"},
            headers=auth_headers,
        )
        job_id = run_resp.json()["id"]
        resp = client.get(f"/api/jobs/{job_id}/result", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["output_path"] is not None
        assert data[0]["operation"] == "blur"

    def test_result_not_found(self, client, auth_headers):
        resp = client.get("/api/jobs/9999/result", headers=auth_headers)
        assert resp.status_code == 404

"""이미지 API (upload, list, get, process, download, delete) + 소유권 테스트."""

import io

from PIL import Image


def _make_upload_file(filename: str = "test.png") -> tuple[str, io.BytesIO, str]:
    """테스트용 PNG 이미지 파일을 메모리에서 생성한다."""
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), color="blue").save(buf, format="PNG")
    buf.seek(0)
    return (filename, buf, "image/png")


class TestUpload:
    def test_upload_image(self, client, auth_headers):
        """이미지 업로드 → 200 + id, filename 반환."""
        resp = client.post(
            "/api/images/upload",
            headers=auth_headers,
            files={"file": _make_upload_file()},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["filename"] == "test.png"


class TestListAndGet:
    def test_list_images(self, client, auth_headers):
        """본인 이미지만 목록에 나온다."""
        client.post(
            "/api/images/upload",
            headers=auth_headers,
            files={"file": _make_upload_file("a.png")},
        )
        resp = client.get("/api/images/", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_image(self, client, auth_headers):
        """이미지 상세 조회 → 200."""
        upload = client.post(
            "/api/images/upload",
            headers=auth_headers,
            files={"file": _make_upload_file()},
        )
        image_id = upload.json()["id"]

        resp = client.get(f"/api/images/{image_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == image_id


class TestProcess:
    def test_process_image(self, client, auth_headers):
        """이미지 처리 → 200 + status=completed."""
        upload = client.post(
            "/api/images/upload",
            headers=auth_headers,
            files={"file": _make_upload_file()},
        )
        image_id = upload.json()["id"]

        resp = client.post(
            f"/api/images/{image_id}/process",
            headers=auth_headers,
            json={"operation": "blur", "params": {"radius": 3}},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_download_not_processed(self, client, auth_headers):
        """미처리 이미지 다운로드 → 400 IMAGE_NOT_PROCESSED."""
        upload = client.post(
            "/api/images/upload",
            headers=auth_headers,
            files={"file": _make_upload_file()},
        )
        image_id = upload.json()["id"]

        resp = client.get(
            f"/api/images/{image_id}/download", headers=auth_headers
        )
        assert resp.status_code == 400
        assert resp.json()["error_code"] == "IMAGE_NOT_PROCESSED"


class TestDelete:
    def test_delete_image(self, client, auth_headers):
        """이미지 삭제 → 200."""
        upload = client.post(
            "/api/images/upload",
            headers=auth_headers,
            files={"file": _make_upload_file()},
        )
        image_id = upload.json()["id"]

        resp = client.delete(f"/api/images/{image_id}", headers=auth_headers)
        assert resp.status_code == 200

        # 삭제 후 조회 → 404
        resp = client.get(f"/api/images/{image_id}", headers=auth_headers)
        assert resp.status_code == 404


class TestAuthRequired:
    def test_list_without_token(self, client):
        """토큰 없이 목록 조회 → 401."""
        resp = client.get("/api/images/")
        assert resp.status_code == 401

    def test_upload_without_token(self, client):
        """토큰 없이 업로드 → 401."""
        resp = client.post(
            "/api/images/upload",
            files={"file": _make_upload_file()},
        )
        assert resp.status_code == 401


class TestOwnership:
    def test_access_other_user_image(self, client, auth_headers, second_user_headers):
        """타인 이미지 조회 → 403 FORBIDDEN."""
        upload = client.post(
            "/api/images/upload",
            headers=auth_headers,
            files={"file": _make_upload_file()},
        )
        image_id = upload.json()["id"]

        resp = client.get(
            f"/api/images/{image_id}", headers=second_user_headers
        )
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "FORBIDDEN"

    def test_process_other_user_image(self, client, auth_headers, second_user_headers):
        """타인 이미지 처리 → 403 FORBIDDEN."""
        upload = client.post(
            "/api/images/upload",
            headers=auth_headers,
            files={"file": _make_upload_file()},
        )
        image_id = upload.json()["id"]

        resp = client.post(
            f"/api/images/{image_id}/process",
            headers=second_user_headers,
            json={"operation": "blur"},
        )
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "FORBIDDEN"

    def test_delete_other_user_image(self, client, auth_headers, second_user_headers):
        """타인 이미지 삭제 → 403 FORBIDDEN."""
        upload = client.post(
            "/api/images/upload",
            headers=auth_headers,
            files={"file": _make_upload_file()},
        )
        image_id = upload.json()["id"]

        resp = client.delete(
            f"/api/images/{image_id}", headers=second_user_headers
        )
        assert resp.status_code == 403
        assert resp.json()["error_code"] == "FORBIDDEN"

    def test_other_user_list_is_empty(self, client, auth_headers, second_user_headers):
        """다른 유저의 이미지는 목록에 보이지 않는다."""
        client.post(
            "/api/images/upload",
            headers=auth_headers,
            files={"file": _make_upload_file()},
        )

        resp = client.get("/api/images/", headers=second_user_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_image_not_found(self, client, auth_headers):
        """존재하지 않는 이미지 조회 → 404 IMAGE_NOT_FOUND."""
        resp = client.get("/api/images/99999", headers=auth_headers)
        assert resp.status_code == 404
        assert resp.json()["error_code"] == "IMAGE_NOT_FOUND"

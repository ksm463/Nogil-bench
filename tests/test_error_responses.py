"""커스텀 에러 응답 형식 검증 테스트.

모든 에러가 {"error_code": "...", "message": "..."} 형식인지 확인한다.
"""


def test_error_has_error_code_and_message(client):
    """에러 응답에 error_code + message 필드가 존재한다."""
    # 존재하지 않는 이메일로 로그인 → 401
    resp = client.post(
        "/auth/login",
        data={"username": "nobody@test.com", "password": "x"},
    )
    data = resp.json()
    assert "error_code" in data, f"error_code 필드 없음: {data}"
    assert "message" in data, f"message 필드 없음: {data}"
    assert isinstance(data["error_code"], str)
    assert isinstance(data["message"], str)


def test_duplicate_email_error_format(client):
    """409 응답이 커스텀 형식을 따른다."""
    payload = {"email": "fmt@test.com", "password": "pass"}
    client.post("/auth/register", json=payload)

    resp = client.post("/auth/register", json=payload)
    assert resp.status_code == 409
    data = resp.json()
    assert data["error_code"] == "DUPLICATE_EMAIL"
    assert len(data["message"]) > 0


def test_invalid_token_error_format(client):
    """잘못된 토큰 → 401 + INVALID_TOKEN 형식."""
    resp = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert resp.status_code == 401
    data = resp.json()
    assert data["error_code"] == "INVALID_TOKEN"
    assert "message" in data


def test_invalid_operation_error_format(client, auth_headers):
    """지원하지 않는 작업 → 400 + INVALID_OPERATION 형식."""
    import io
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (10, 10), "red").save(buf, format="PNG")
    buf.seek(0)

    upload = client.post(
        "/api/images/upload",
        headers=auth_headers,
        files={"file": ("t.png", buf, "image/png")},
    )
    image_id = upload.json()["id"]

    resp = client.post(
        f"/api/images/{image_id}/process",
        headers=auth_headers,
        json={"operation": "nonexistent_op"},
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data["error_code"] == "INVALID_OPERATION"
    assert "message" in data

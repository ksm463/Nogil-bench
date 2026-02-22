"""인증 API (register, login, me) 테스트."""


class TestRegister:
    def test_register_success(self, client):
        """신규 가입 → 201 + id, email 반환."""
        resp = client.post(
            "/auth/register",
            json={"email": "new@test.com", "password": "pass1234"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "new@test.com"
        assert "id" in data

    def test_register_duplicate_email(self, client):
        """중복 이메일 → 409 DUPLICATE_EMAIL."""
        payload = {"email": "dup@test.com", "password": "pass1234"}
        client.post("/auth/register", json=payload)

        resp = client.post("/auth/register", json=payload)
        assert resp.status_code == 409
        assert resp.json()["error_code"] == "DUPLICATE_EMAIL"

    def test_register_invalid_email(self, client):
        """잘못된 이메일 형식 → 422 (pydantic 검증)."""
        resp = client.post(
            "/auth/register",
            json={"email": "not-an-email", "password": "pass1234"},
        )
        assert resp.status_code == 422


class TestLogin:
    def test_login_success(self, client):
        """정상 로그인 → 200 + access_token 반환."""
        client.post(
            "/auth/register",
            json={"email": "login@test.com", "password": "pass1234"},
        )
        resp = client.post(
            "/auth/login",
            data={"username": "login@test.com", "password": "pass1234"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        """잘못된 패스워드 → 401 INVALID_CREDENTIALS."""
        client.post(
            "/auth/register",
            json={"email": "wp@test.com", "password": "correct"},
        )
        resp = client.post(
            "/auth/login",
            data={"username": "wp@test.com", "password": "wrong"},
        )
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "INVALID_CREDENTIALS"

    def test_login_nonexistent_email(self, client):
        """존재하지 않는 이메일 → 401 INVALID_CREDENTIALS."""
        resp = client.post(
            "/auth/login",
            data={"username": "nobody@test.com", "password": "pass"},
        )
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "INVALID_CREDENTIALS"


class TestMe:
    def test_me_with_valid_token(self, client, auth_headers):
        """유효한 토큰으로 /me → 200 + email 반환."""
        resp = client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert "email" in data

    def test_me_without_token(self, client):
        """토큰 없이 /me → 401."""
        resp = client.get("/auth/me")
        assert resp.status_code == 401

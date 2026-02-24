"""벤치마크 API 테스트.

POST /api/benchmarks/run  — 벤치마크 실행 + 결과 저장
GET  /api/benchmarks/      — 결과 목록
GET  /api/benchmarks/{id}  — 결과 상세
GET  /api/benchmarks/compare — 여러 결과 비교
"""


class TestRunBenchmark:
    def test_run_sync(self, client, auth_headers):
        resp = client.post(
            "/api/benchmarks/run",
            json={"method": "sync", "operation": "blur", "image_count": 2},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["method"] == "sync"
        assert data["operation"] == "blur"
        assert data["workers"] == 1  # sync는 항상 1
        assert data["image_count"] == 2
        assert data["duration"] > 0
        assert data["id"] is not None

    def test_run_threading(self, client, auth_headers):
        resp = client.post(
            "/api/benchmarks/run",
            json={"method": "threading", "operation": "blur", "workers": 2, "image_count": 2},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["method"] == "threading"
        assert data["workers"] == 2

    def test_run_multiprocessing(self, client, auth_headers):
        resp = client.post(
            "/api/benchmarks/run",
            json={"method": "multiprocessing", "operation": "blur", "workers": 2, "image_count": 2},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["method"] == "multiprocessing"

    def test_run_frethread(self, client, auth_headers):
        resp = client.post(
            "/api/benchmarks/run",
            json={"method": "frethread", "operation": "blur", "workers": 2, "image_count": 2},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["method"] == "frethread"

    def test_run_invalid_method(self, client, auth_headers):
        resp = client.post(
            "/api/benchmarks/run",
            json={"method": "invalid", "operation": "blur", "image_count": 2},
            headers=auth_headers,
        )
        assert resp.status_code == 422  # Literal 타입 검증 → Pydantic 422

    def test_run_invalid_operation(self, client, auth_headers):
        resp = client.post(
            "/api/benchmarks/run",
            json={"method": "sync", "operation": "invalid", "image_count": 2},
            headers=auth_headers,
        )
        assert resp.status_code == 422  # Literal 타입 검증 → Pydantic 422

    def test_run_without_auth(self, client):
        resp = client.post(
            "/api/benchmarks/run",
            json={"method": "sync", "operation": "blur", "image_count": 2},
        )
        assert resp.status_code == 401


class TestListBenchmarks:
    def test_list_empty(self, client, auth_headers):
        resp = client.get("/api/benchmarks/", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_after_run(self, client, auth_headers):
        client.post(
            "/api/benchmarks/run",
            json={"method": "sync", "operation": "blur", "image_count": 2},
            headers=auth_headers,
        )
        resp = client.get("/api/benchmarks/", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_list_only_own(self, client, auth_headers, second_user_headers):
        """다른 사용자의 벤치마크는 보이지 않는다."""
        client.post(
            "/api/benchmarks/run",
            json={"method": "sync", "operation": "blur", "image_count": 2},
            headers=auth_headers,
        )
        resp = client.get("/api/benchmarks/", headers=second_user_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 0


class TestGetBenchmark:
    def test_get_detail(self, client, auth_headers):
        run_resp = client.post(
            "/api/benchmarks/run",
            json={"method": "sync", "operation": "blur", "image_count": 2},
            headers=auth_headers,
        )
        bid = run_resp.json()["id"]
        resp = client.get(f"/api/benchmarks/{bid}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == bid

    def test_get_not_found(self, client, auth_headers):
        resp = client.get("/api/benchmarks/9999", headers=auth_headers)
        assert resp.status_code == 404
        assert resp.json()["error_code"] == "BENCHMARK_NOT_FOUND"

    def test_get_other_user(self, client, auth_headers, second_user_headers):
        """다른 사용자의 벤치마크는 404."""
        run_resp = client.post(
            "/api/benchmarks/run",
            json={"method": "sync", "operation": "blur", "image_count": 2},
            headers=auth_headers,
        )
        bid = run_resp.json()["id"]
        resp = client.get(f"/api/benchmarks/{bid}", headers=second_user_headers)
        assert resp.status_code == 404


class TestCompareBenchmarks:
    def test_compare_two(self, client, auth_headers):
        r1 = client.post(
            "/api/benchmarks/run",
            json={"method": "sync", "operation": "blur", "image_count": 2},
            headers=auth_headers,
        ).json()
        r2 = client.post(
            "/api/benchmarks/run",
            json={"method": "threading", "operation": "blur", "workers": 2, "image_count": 2},
            headers=auth_headers,
        ).json()

        resp = client.get(
            "/api/benchmarks/compare",
            params={"ids": [r1["id"], r2["id"]]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        methods = {d["method"] for d in data}
        assert methods == {"sync", "threading"}

    def test_compare_not_found(self, client, auth_headers):
        resp = client.get(
            "/api/benchmarks/compare",
            params={"ids": [9999]},
            headers=auth_headers,
        )
        assert resp.status_code == 404

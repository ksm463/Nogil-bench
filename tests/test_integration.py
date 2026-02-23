"""통합 테스트 — 전체 플로우를 하나의 시나리오로 검증.

1. 이미지 업로드 → 배치 작업 → 상태 확인 → 결과 확인
2. 벤치마크 실행 → 목록 → 비교
"""

from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _upload_image(client, auth_headers, filename="test_cat.png"):
    with open(FIXTURES_DIR / filename, "rb") as f:
        resp = client.post(
            "/api/images/upload",
            files={"file": (filename, f, "image/png")},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    return resp.json()["id"]


class TestBatchFlow:
    """이미지 업로드 → 배치 작업 생성 → 상태 완료 확인 → 결과 다운로드."""

    def test_full_batch_flow(self, client, auth_headers):
        # 1. 이미지 업로드
        img1 = _upload_image(client, auth_headers, "test_cat.png")
        img2 = _upload_image(client, auth_headers, "test_landscape.png")

        # 2. 배치 작업 생성 (202 Accepted)
        batch_resp = client.post(
            "/api/jobs/batch",
            json={
                "image_ids": [img1, img2],
                "operation": "blur",
                "params": {"radius": 5},
            },
            headers=auth_headers,
        )
        assert batch_resp.status_code == 202
        job_id = batch_resp.json()["id"]

        # 3. 작업 상태 확인 (TestClient에서 BackgroundTasks 동기 실행)
        status_resp = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
        assert status_resp.status_code == 200
        job_data = status_resp.json()
        assert job_data["status"] == "completed"
        assert job_data["processed_count"] == 2
        assert job_data["duration"] > 0

        # 4. 작업 결과 확인
        result_resp = client.get(f"/api/jobs/{job_id}/result", headers=auth_headers)
        assert result_resp.status_code == 200
        results = result_resp.json()
        assert len(results) == 2
        assert all(r["output_path"] is not None for r in results)
        assert all(r["operation"] == "blur" for r in results)

        # 5. 작업 목록에서도 확인
        list_resp = client.get("/api/jobs/", headers=auth_headers)
        assert len(list_resp.json()) == 1


class TestBenchmarkFlow:
    """벤치마크 실행 → 목록 조회 → 비교."""

    def test_run_and_compare(self, client, auth_headers):
        # 1. sync 벤치마크
        r1 = client.post(
            "/api/benchmarks/run",
            json={"method": "sync", "operation": "blur", "image_count": 2},
            headers=auth_headers,
        )
        assert r1.status_code == 201
        id1 = r1.json()["id"]
        sync_duration = r1.json()["duration"]

        # 2. threading 벤치마크
        r2 = client.post(
            "/api/benchmarks/run",
            json={"method": "threading", "operation": "blur", "workers": 2, "image_count": 2},
            headers=auth_headers,
        )
        assert r2.status_code == 201
        id2 = r2.json()["id"]

        # 3. 목록에 2건
        list_resp = client.get("/api/benchmarks/", headers=auth_headers)
        assert len(list_resp.json()) == 2

        # 4. 비교
        compare_resp = client.get(
            "/api/benchmarks/compare",
            params={"ids": [id1, id2]},
            headers=auth_headers,
        )
        assert compare_resp.status_code == 200
        data = compare_resp.json()
        assert len(data) == 2
        methods = {d["method"] for d in data}
        assert methods == {"sync", "threading"}

        # 5. 상세 조회
        detail_resp = client.get(f"/api/benchmarks/{id1}", headers=auth_headers)
        assert detail_resp.status_code == 200
        assert detail_resp.json()["duration"] == sync_duration


class TestBenchmarkAllMethods:
    """4가지 방식 모두 API를 통해 실행 가능한지 검증."""

    def test_all_four_methods(self, client, auth_headers):
        methods = ["sync", "threading", "multiprocessing", "frethread"]
        ids = []

        for method in methods:
            body = {"method": method, "operation": "blur", "image_count": 2}
            if method != "sync":
                body["workers"] = 2
            resp = client.post(
                "/api/benchmarks/run", json=body, headers=auth_headers
            )
            assert resp.status_code == 201, f"{method} failed: {resp.json()}"
            assert resp.json()["duration"] > 0
            ids.append(resp.json()["id"])

        # 4건 모두 비교
        compare_resp = client.get(
            "/api/benchmarks/compare",
            params={"ids": ids},
            headers=auth_headers,
        )
        assert compare_resp.status_code == 200
        assert len(compare_resp.json()) == 4

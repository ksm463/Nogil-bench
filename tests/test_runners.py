"""processor 러너 모듈 테스트.

sync_runner, thread_runner, mp_runner, frethread_runner가
동일한 인터페이스로 동작하고 올바른 결과를 반환하는지 검증한다.
"""

import sys
from pathlib import Path

import pytest
from PIL import Image

from processor import sync_runner, thread_runner, mp_runner, frethread_runner


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def image_paths():
    """테스트용 이미지 경로 목록."""
    paths = sorted(str(p) for p in FIXTURES_DIR.glob("*.png"))
    assert len(paths) > 0, f"No test images found in {FIXTURES_DIR}"
    return paths


class TestSyncRunner:
    def test_returns_images(self, image_paths):
        results = sync_runner.run(image_paths, "blur", {"radius": 3})
        assert len(results) == len(image_paths)
        assert all(isinstance(r, Image.Image) for r in results)

    def test_resize(self, image_paths):
        results = sync_runner.run(image_paths, "resize", {"width": 100, "height": 100})
        assert all(r.size == (100, 100) for r in results)


class TestThreadRunner:
    def test_returns_images(self, image_paths):
        results = thread_runner.run(image_paths, "blur", {"radius": 3}, workers=2)
        assert len(results) == len(image_paths)
        assert all(isinstance(r, Image.Image) for r in results)

    def test_resize(self, image_paths):
        results = thread_runner.run(image_paths, "resize", {"width": 50, "height": 50}, workers=2)
        assert all(r.size == (50, 50) for r in results)

    def test_single_worker(self, image_paths):
        results = thread_runner.run(image_paths, "grayscale", workers=1)
        assert len(results) == len(image_paths)


class TestMpRunner:
    def test_returns_images(self, image_paths):
        results = mp_runner.run(image_paths, "blur", {"radius": 3}, workers=2)
        assert len(results) == len(image_paths)
        assert all(isinstance(r, Image.Image) for r in results)

    def test_resize(self, image_paths):
        results = mp_runner.run(image_paths, "resize", {"width": 80, "height": 80}, workers=2)
        assert all(r.size == (80, 80) for r in results)


class TestFrethreadRunner:
    def test_requires_gil_disabled(self):
        """GIL=0 환경에서만 실행 가능한지 확인."""
        if sys._is_gil_enabled():
            with pytest.raises(RuntimeError, match="GIL이 비활성화된"):
                frethread_runner.run(["/nonexistent"], "blur")
        else:
            pytest.skip("GIL이 이미 비활성화된 환경 — 에러 경로 테스트 불가")

    def test_returns_images(self, image_paths):
        if sys._is_gil_enabled():
            pytest.skip("GIL=0 환경에서만 실행 가능")
        results = frethread_runner.run(image_paths, "blur", {"radius": 3}, workers=2)
        assert len(results) == len(image_paths)
        assert all(isinstance(r, Image.Image) for r in results)

    def test_resize(self, image_paths):
        if sys._is_gil_enabled():
            pytest.skip("GIL=0 환경에서만 실행 가능")
        results = frethread_runner.run(image_paths, "resize", {"width": 60, "height": 60}, workers=2)
        assert all(r.size == (60, 60) for r in results)


class TestRunnerConsistency:
    """모든 러너가 동일한 결과를 반환하는지 비교."""

    def test_all_runners_same_output_size(self, image_paths):
        params = {"width": 120, "height": 120}
        sync_results = sync_runner.run(image_paths, "resize", params)
        thread_results = thread_runner.run(image_paths, "resize", params, workers=2)
        mp_results = mp_runner.run(image_paths, "resize", params, workers=2)

        assert len(sync_results) == len(thread_results) == len(mp_results)
        for s, t, m in zip(sync_results, thread_results, mp_results):
            assert s.size == t.size == m.size == (120, 120)

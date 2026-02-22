"""이미지 처리 함수 단위 테스트."""

from PIL import Image

from processor.operations import blur, grayscale, resize


def _make_image(width: int = 100, height: int = 100) -> Image.Image:
    """테스트용 RGB 이미지를 메모리에서 생성한다."""
    return Image.new("RGB", (width, height), color="red")


def test_resize():
    """resize 후 지정한 크기와 일치한다."""
    img = _make_image(100, 100)
    result = resize(img, width=50, height=30)

    assert result.size == (50, 30)


def test_blur():
    """blur 적용 후 같은 크기의 Image를 반환한다."""
    img = _make_image(80, 60)
    result = blur(img, radius=3)

    assert isinstance(result, Image.Image)
    assert result.size == (80, 60)


def test_grayscale():
    """grayscale 적용 후 RGB 모드로 반환된다 (내부에서 L→RGB 변환)."""
    img = _make_image(50, 50)
    result = grayscale(img)

    assert result.mode == "RGB"
    assert result.size == (50, 50)
    # 단색 빨간 이미지를 그레이스케일하면 모든 채널이 동일해야 한다
    r, g, b = result.getpixel((0, 0))
    assert r == g == b

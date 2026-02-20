"""
순수 CPU-bound 이미지 처리 함수.
모든 함수는 PIL.Image를 받아서 PIL.Image를 반환한다.
"""

from PIL import Image, ImageDraw, ImageFilter, ImageFont


def resize(image: Image.Image, width: int, height: int) -> Image.Image:
    return image.resize((width, height), Image.LANCZOS)


def blur(image: Image.Image, radius: int = 5) -> Image.Image:
    return image.filter(ImageFilter.GaussianBlur(radius=radius))


def sharpen(image: Image.Image) -> Image.Image:
    return image.filter(ImageFilter.SHARPEN)


def grayscale(image: Image.Image) -> Image.Image:
    return image.convert("L").convert("RGB")


def rotate(image: Image.Image, degrees: int = 90) -> Image.Image:
    return image.rotate(degrees, expand=True)


def watermark(image: Image.Image, text: str = "nogil-bench") -> Image.Image:
    overlay = image.copy()
    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
    except OSError:
        font = ImageFont.load_default(size=36)

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    x = image.width - text_w - 20
    y = image.height - text_h - 20

    draw.text((x, y), text, fill=(255, 255, 255, 128), font=font)
    return overlay

import base64
import io

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_SIDE_PX = 1568
JPEG_QUALITY = 85


class InvalidImageError(ValueError):
    pass


def to_jpeg(data: bytes) -> bytes:
    """Fix phone rotation, shrink and convert to JPEG bytes."""
    try:
        image = Image.open(io.BytesIO(data))
        image = ImageOps.exif_transpose(image)
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError("File is not a valid image") from exc

    if image.mode != "RGB":
        image = image.convert("RGB")

    image.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX))

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY)
    return buffer.getvalue()


def prepare_image(data: bytes) -> str:
    """Return the image as base64 JPEG, ready for the Claude API."""
    return base64.standard_b64encode(to_jpeg(data)).decode("utf-8")
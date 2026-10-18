import base64
import io

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_SIDE_PX = 1568
JPEG_QUALITY = 85


class InvalidImageError(ValueError):
    pass


def prepare_image(data: bytes) -> str:
    """Fix phone rotation, shrink, convert to JPEG and return base64."""
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
    return base64.standard_b64encode(buffer.getvalue()).decode("utf-8")
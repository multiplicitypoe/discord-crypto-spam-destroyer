from __future__ import annotations

from io import BytesIO
from typing import Iterable

from PIL import Image
import imagehash

Image.MAX_IMAGE_PIXELS = 100_000_000

def compute_phash(image_bytes: bytes) -> str:
    with Image.open(BytesIO(image_bytes)) as image:
        return str(imagehash.phash(image))


def compute_phashes(images: Iterable[bytes]) -> list[str]:
    hashes: list[str] = []
    for image_bytes in images:
        try:
            hashes.append(compute_phash(image_bytes))
        except (OSError, ValueError):
            continue
    return hashes

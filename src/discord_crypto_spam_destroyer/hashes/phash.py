from __future__ import annotations

import logging
from io import BytesIO
from typing import Iterable

from PIL import Image
import imagehash

logger = logging.getLogger(__name__)

Image.MAX_IMAGE_PIXELS = 100_000_000

def compute_phash(image_bytes: bytes) -> str:
    with Image.open(BytesIO(image_bytes)) as image:
        return str(imagehash.phash(image))


def compute_phashes(images: Iterable[bytes]) -> list[str]:
    hashes: list[str] = []
    for image_bytes in images:
        try:
            hashes.append(compute_phash(image_bytes))
        except Exception as exc:
            # Deliberately broad. PIL raises SyntaxError for a broken PNG, which
            # is neither OSError nor ValueError, so it used to escape this loop.
            # Nothing that happens while hashing one attachment should stop the
            # others being checked.
            logger.info(
                "Skipping undecodable image (%s): %s", type(exc).__name__, exc
            )
            continue
    return hashes

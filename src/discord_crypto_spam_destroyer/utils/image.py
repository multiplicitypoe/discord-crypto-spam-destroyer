from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from io import BytesIO
from typing import Iterable

import discord
from PIL import Image

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
ALLOWED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "image/bmp",
}


@dataclass(frozen=True)
class DownloadedImage:
    data: bytes
    content_type: str
    filename: str
    url: str


def resize_image_for_openai(
    image: DownloadedImage,
    max_dim: int,
) -> tuple[bytes, str, int | None, int | None, int | None]:
    if max_dim <= 0:
        try:
            with Image.open(BytesIO(image.data)) as original:
                width, height = original.size
            return image.data, image.content_type, width, height, None
        except Exception:
            return image.data, image.content_type, None, None, None
    try:
        with Image.open(BytesIO(image.data)) as original:
            original = original.convert("RGB")
            width, height = original.size
            if max(width, height) <= max_dim:
                return image.data, image.content_type, width, height, None
            scale = max_dim / float(max(width, height))
            resized = original.resize(
                (int(width * scale), int(height * scale)),
                resample=Image.Resampling.LANCZOS,
            )
            buffer = BytesIO()
            resized.save(buffer, format="JPEG", quality=82, optimize=True)
            return buffer.getvalue(), "image/jpeg", resized.width, resized.height, 82
    except Exception:
        return image.data, image.content_type, None, None, None


def is_image_attachment(attachment: discord.Attachment) -> bool:
    content_type = attachment.content_type
    if content_type:
        normalized = content_type.split(";", 1)[0].strip()
        return normalized in ALLOWED_IMAGE_TYPES
    return attachment.filename.lower().endswith(IMAGE_EXTENSIONS)


async def read_attachment(
    attachment: discord.Attachment,
    max_bytes: int,
    timeout_s: float,
) -> DownloadedImage | None:
    if attachment.size and attachment.size > max_bytes:
        return None
    try:
        data = await asyncio.wait_for(attachment.read(), timeout=timeout_s)
    except (asyncio.TimeoutError, discord.HTTPException, discord.NotFound):
        return None
    if len(data) > max_bytes:
        return None
    return DownloadedImage(
        data=data,
        content_type=attachment.content_type or "image/png",
        filename=attachment.filename or "image.png",
        url=attachment.url,
    )


def to_data_url(
    image: DownloadedImage,
    max_dim: int,
) -> tuple[str, int, str, int | None, int | None, int | None]:
    resized, content_type, width, height, quality = resize_image_for_openai(image, max_dim)
    encoded = base64.b64encode(resized).decode("ascii")
    return f"data:{content_type};base64,{encoded}", len(resized), content_type, width, height, quality


def build_discord_files(images: Iterable[DownloadedImage]) -> list[discord.File]:
    files: list[discord.File] = []
    for index, image in enumerate(images, start=1):
        filename = image.filename or f"image_{index}.png"
        files.append(discord.File(fp=BytesIO(image.data), filename=filename))
    return files

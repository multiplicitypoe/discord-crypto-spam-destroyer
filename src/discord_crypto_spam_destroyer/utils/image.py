from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from io import BytesIO
from typing import Iterable

import discord

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")


@dataclass(frozen=True)
class DownloadedImage:
    data: bytes
    content_type: str
    filename: str
    url: str


def is_image_attachment(attachment: discord.Attachment) -> bool:
    content_type = attachment.content_type or ""
    if content_type.startswith("image/"):
        return True
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


def to_data_url(image: DownloadedImage) -> str:
    encoded = base64.b64encode(image.data).decode("ascii")
    return f"data:{image.content_type};base64,{encoded}"


def build_discord_files(images: Iterable[DownloadedImage]) -> list[discord.File]:
    files: list[discord.File] = []
    for index, image in enumerate(images, start=1):
        filename = image.filename or f"image_{index}.png"
        files.append(discord.File(fp=BytesIO(image.data), filename=filename))
    return files

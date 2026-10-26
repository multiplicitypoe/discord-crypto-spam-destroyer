from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from discord_crypto_spam_destroyer.moderation.whitelist import is_channel_in_list


@dataclass(frozen=True)
class ImageSelection:
    qualifies: bool
    selected_urls: Sequence[str]
    total_images: int


def select_images(attachment_urls: Sequence[str], min_count: int, max_count: int) -> ImageSelection:
    total = len(attachment_urls)
    if total < min_count:
        return ImageSelection(qualifies=False, selected_urls=[], total_images=total)

    selected = list(attachment_urls[:max_count])
    return ImageSelection(qualifies=True, selected_urls=selected, total_images=total)


def min_images_for_channel(
    min_image_count: int,
    channel_id: int,
    parent_id: int | None,
    category_id: int | None,
    full_scan_channels: tuple[int, ...],
) -> int:
    """How many images a post needs before the OpenAI scan runs in this channel.

    Normally that is ``min_image_count``. In a full-scan channel every post with
    an image qualifies, so one image is enough. Threads and forum posts inherit
    from their parent channel, and channels from their category, the same way
    the allowlist and ignorelist do.
    """
    if full_scan_channels and is_channel_in_list(channel_id, parent_id, category_id, full_scan_channels) is not None:
        return min(min_image_count, 1)
    return min_image_count

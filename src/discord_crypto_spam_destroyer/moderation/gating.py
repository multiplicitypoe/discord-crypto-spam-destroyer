from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


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

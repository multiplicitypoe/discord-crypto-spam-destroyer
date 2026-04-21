from __future__ import annotations


def is_channel_in_list(
    channel_id: int,
    parent_id: int | None,
    category_id: int | None,
    id_list: tuple[int, ...],
) -> int | None:
    """Return the matched id, or ``None`` if no match.

    Walks the channel hierarchy:
      channel → parent (threads/forum posts) → category.
    """
    if channel_id in id_list:
        return channel_id
    if parent_id is not None and parent_id in id_list:
        return parent_id
    if category_id is not None and category_id in id_list:
        return category_id
    return None

from discord_crypto_spam_destroyer.moderation.gating import select_images


def test_select_images_not_enough() -> None:
    selection = select_images(["a", "b"], min_count=3, max_count=4)
    assert selection.qualifies is False
    assert selection.selected_urls == []
    assert selection.total_images == 2


def test_select_images_selects_subset() -> None:
    selection = select_images(["a", "b", "c", "d"], min_count=3, max_count=2)
    assert selection.qualifies is True
    assert selection.selected_urls == ["a", "b"]
    assert selection.total_images == 4

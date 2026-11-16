"""The report card is informative: it says what was removed, how fast and why.

Confidence, an empty indicators line and an empty to-do line are left off, the
message link is the title, and the only button is Add hashes, shown only when
there are images to add.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

from discord_crypto_spam_destroyer.discord_ui.mod_report import (
    ADD_HASHES_ID,
    HashActions,
    ReportCard,
    attachment_names,
    card_text,
    describe_outcome,
    suggested_next_step,
)
from discord_crypto_spam_destroyer.utils.image import DownloadedImage


def _card(**overrides):
    message = SimpleNamespace(
        jump_url="https://discord.com/channels/1/2/3",
        channel=SimpleNamespace(mention="<#2>"),
        created_at=datetime(2026, 11, 16, 14, 30, tzinfo=timezone.utc),
    )
    author = SimpleNamespace(mention="<@9>", name="spammer", id=9,
                             display_avatar=SimpleNamespace(url="https://cdn.discordapp.com/a.png"))
    args = dict(reason="Known scam image: 4 of 4 images are on the denylist", indicators=None,
                suggestion=None, outcome=describe_outcome(True, 0.52, "softban"),
                deleted=True, needs_review=False)
    args.update(overrides)
    return card_text(message, author, "(Member, PoE-2)", **args)


def _text(view) -> str:
    return "\n".join(getattr(item, "content", "") for item in view.walk_children())


def _actions(new_hashes):
    return HashActions(hash_store=None, all_hashes=["a"], mod_role_id=1, report_store=None, new_hashes=new_hashes)


def test_the_card_says_how_fast_and_why_and_links_the_post():
    text = _text(ReportCard(_card(), ["attachment://image_1.png"], _actions(0)))
    assert "Removed **0.52s** after it was posted · author softbanned" in text
    assert "[Crypto scam removed](https://discord.com/channels/1/2/3)" in text
    assert "4 of 4 images" in text


def test_no_confidence_no_empty_lines():
    text = _text(ReportCard(_card(), [], _actions(0))).lower()
    assert "confidence" not in text
    assert "indicators" not in text
    assert "none" not in text
    assert "to do" not in text


def test_nothing_to_add_means_no_button():
    view = ReportCard(_card(), [], _actions(0))
    assert not view.has_button


def test_new_images_get_a_to_do_line_and_the_add_button():
    view = ReportCard(_card(suggestion=suggested_next_step(2, False)), [], _actions(2))
    assert view.has_button
    assert view.is_persistent()
    assert "**To do:** Add the 2 images" in _text(view)
    labels = [getattr(i, "label", None) for i in view.walk_children() if getattr(i, "custom_id", None) == ADD_HASHES_ID]
    assert labels == ["Add 2 new hashes"]


def test_a_pressed_card_shows_who_did_what_and_loses_the_button():
    view = ReportCard(_card(suggestion="x"), [], None, note="-# <@1>: added 2 hashes to the denylist")
    assert not view.has_button
    assert "added 2 hashes" in _text(view)


def test_outcomes_read_plainly():
    assert describe_outcome(True, 1.234, "no softban (cooldown)") == (
        "Removed **1.23s** after it was posted · author already actioned for an earlier post")
    assert describe_outcome(False, None, "report only (allowlisted)") == "**Not removed** · reported only (allowlisted)"


def test_gallery_names_are_unique_even_when_uploads_share_one():
    images = [DownloadedImage(data=b"", content_type="image/png", filename="image.png", url="u")] * 3
    assert attachment_names(images) == ["image_1.png", "image_2.png", "image_3.png"]


def test_the_layout_stays_inside_discords_limits():
    view = ReportCard(_card(suggestion=suggested_next_step(4, True)),
                      [f"attachment://image_{i}.png" for i in range(1, 5)], _actions(4))
    assert view.total_children_count <= 40
    assert view.content_length() <= 4000


def test_a_redrawn_card_keeps_its_images():
    """A v2 message has no attachments of its own; the URLs live in the gallery."""
    import discord
    from discord_crypto_spam_destroyer.discord_ui.mod_report import gallery_urls

    gallery = discord.MediaGalleryComponent.__new__(discord.MediaGalleryComponent)
    gallery.items = [SimpleNamespace(media=SimpleNamespace(url="https://cdn.discordapp.com/x/1.png"))]
    container = SimpleNamespace(children=[SimpleNamespace(children=None, components=None), gallery])
    message = SimpleNamespace(components=[container], attachments=[])
    assert gallery_urls(message) == ["https://cdn.discordapp.com/x/1.png"]

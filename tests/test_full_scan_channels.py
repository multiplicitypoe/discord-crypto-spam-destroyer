"""Every image post in a full-scan channel gets the OpenAI scan, not just posts
with MIN_IMAGE_COUNT or more images.

Crypto scam bots post in one voice channel's text chat far more than anywhere
else, and some of those posts carry only one or two images. The count gate
exists to keep OpenAI spend down across a busy server, so it stays everywhere
else; a channel listed in FULL_SCAN_CHANNELS skips it.
"""
import asyncio
import io
import json
import random
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from discord_crypto_spam_destroyer import bot as bot_module
from discord_crypto_spam_destroyer.bot import CryptoSpamBot
from discord_crypto_spam_destroyer.config import load_settings, resolve_settings
from discord_crypto_spam_destroyer.hashes.store import FileHashStore
from discord_crypto_spam_destroyer.models import VisionIndicators, VisionResult
from discord_crypto_spam_destroyer.moderation.gating import min_images_for_channel
from discord_crypto_spam_destroyer.utils.image import DownloadedImage

GUILD = 500
FULL_SCAN = 1000
OTHER = 2000
CATEGORY = 3000
FORUM = 4000


# --- the gate ---------------------------------------------------------------

def test_a_full_scan_channel_needs_only_one_image() -> None:
    assert min_images_for_channel(3, FULL_SCAN, None, None, (FULL_SCAN,)) == 1


def test_other_channels_keep_the_configured_minimum() -> None:
    assert min_images_for_channel(3, OTHER, None, None, (FULL_SCAN,)) == 3
    assert min_images_for_channel(3, OTHER, None, None, ()) == 3


def test_threads_and_categories_inherit_like_the_other_lists() -> None:
    assert min_images_for_channel(3, 9, FULL_SCAN, None, (FULL_SCAN,)) == 1
    assert min_images_for_channel(3, 9, None, CATEGORY, (CATEGORY,)) == 1


def test_a_minimum_already_below_one_is_left_alone() -> None:
    assert min_images_for_channel(0, FULL_SCAN, None, None, (FULL_SCAN,)) == 0


# --- settings ---------------------------------------------------------------

@pytest.fixture
def env(monkeypatch, tmp_path):
    for key in ("MULTI_SERVER_CONFIG_PATH", "FULL_SCAN_CHANNELS"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("MOD_CHANNEL", "1")
    monkeypatch.setenv("MOD_ROLE_ID", "2")
    monkeypatch.setenv("KNOWN_BAD_HASH_PATH", str(tmp_path / "bad_hashes.txt"))
    return monkeypatch


def test_full_scan_channels_default_to_none(env) -> None:
    assert resolve_settings(load_settings(), GUILD).full_scan_channels == ()


def test_env_var_lists_the_channels(env) -> None:
    env.setenv("FULL_SCAN_CHANNELS", f"{FULL_SCAN}, {FORUM}")
    assert resolve_settings(load_settings(), GUILD).full_scan_channels == (FULL_SCAN, FORUM)


def test_a_servers_own_list_overrides_the_env_var(env, tmp_path) -> None:
    config = tmp_path / "multi.json"
    config.write_text(json.dumps({
        str(GUILD): {"mod_channel": "1", "mod_role_id": 2, "full_scan_channels": [FULL_SCAN]},
        "501": {"mod_channel": "1", "mod_role_id": 2},
    }))
    env.setenv("MULTI_SERVER_CONFIG_PATH", str(config))
    env.setenv("FULL_SCAN_CHANNELS", str(FORUM))
    settings = load_settings()
    assert resolve_settings(settings, GUILD).full_scan_channels == (FULL_SCAN,)
    # A server that does not set it falls back to the env var.
    assert resolve_settings(settings, 501).full_scan_channels == (FORUM,)
    # And a server we have no entry for gets the env var too.
    assert resolve_settings(settings, 999).full_scan_channels == (FORUM,)


# --- the bot ----------------------------------------------------------------

def _png(seed: int) -> bytes:
    rng = random.Random(seed)
    image = Image.new("RGB", (64, 64))
    image.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(64 * 64)])
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _message(n_images: int, channel_id: int, parent_id: int | None = None, category_id: int | None = None):
    attachments = [
        SimpleNamespace(content_type="image/png", filename=f"{i}.png", size=1000, url=f"https://cdn.test/{i}.png", seed=i)
        for i in range(n_images)
    ]
    return SimpleNamespace(
        id=77,
        guild=SimpleNamespace(id=GUILD),
        author=SimpleNamespace(bot=False, id=8, roles=[]),
        attachments=attachments,
        channel=SimpleNamespace(id=channel_id, parent_id=parent_id, category_id=category_id, name="chat"),
    )


@pytest.fixture
def harness(env, tmp_path, monkeypatch):
    """A bot with Discord, OpenAI, and the mod actions replaced by recorders."""
    env.setenv("FULL_SCAN_CHANNELS", str(FULL_SCAN))
    (tmp_path / "bad_hashes.txt").write_text("")

    bot = CryptoSpamBot.__new__(CryptoSpamBot)
    bot.settings = load_settings()
    bot.hash_store = FileHashStore(Path(tmp_path / "bad_hashes.txt"))
    bot._settings_cache = {}
    events: dict[str, list] = {"classified": [], "deleted": [], "actions": []}

    async def read_attachment(attachment, max_bytes, timeout_s):
        return DownloadedImage(data=_png(attachment.seed), content_type="image/png",
                               filename=attachment.filename, url=attachment.url)

    async def classify(message_id, settings, downloaded):
        events["classified"].append(len(downloaded))
        return VisionResult(is_crypto_scam=True, confidence=0.95, reasons=["test"],
                            indicators=VisionIndicators(domains=[], amounts=[], wallet_addresses=[]))

    async def delete(message):
        events["deleted"].append(message.id)
        return True

    async def roles(guild, author):
        return "(test)"

    async def act(guild, author, **kwargs):
        events["actions"].append(kwargs["reason"])
        return "softban"

    monkeypatch.setattr(bot_module, "read_attachment", read_attachment)
    monkeypatch.setattr(bot_module, "safe_delete", delete)
    bot._classify_images = classify
    bot._format_author_roles = roles
    bot._apply_high_action_with_mod_check = act
    bot._report_allowed = lambda *a, **k: False  # nothing to send the mod channel in a test
    return bot, events


def run(bot, message) -> None:
    asyncio.run(bot.on_message(message))


def test_a_single_image_in_the_full_scan_channel_is_scanned_and_actioned(harness) -> None:
    bot, events = harness
    run(bot, _message(1, FULL_SCAN))
    assert events["classified"] == [1]
    assert events["deleted"] == [77]
    assert events["actions"] == ["High confidence crypto scam"]


def test_two_images_in_the_full_scan_channel_are_scanned(harness) -> None:
    bot, events = harness
    run(bot, _message(2, FULL_SCAN))
    assert events["classified"] == [2]


def test_a_thread_under_the_full_scan_channel_is_scanned(harness) -> None:
    bot, events = harness
    run(bot, _message(1, 9999, parent_id=FULL_SCAN))
    assert events["classified"] == [1]


def test_one_or_two_images_elsewhere_are_still_not_sent_to_openai(harness) -> None:
    bot, events = harness
    run(bot, _message(1, OTHER))
    run(bot, _message(2, OTHER))
    assert events["classified"] == []
    assert events["deleted"] == []


def test_three_images_elsewhere_are_still_scanned(harness) -> None:
    bot, events = harness
    run(bot, _message(3, OTHER))
    assert events["classified"] == [3]


def test_hash_only_mode_still_means_no_openai_even_in_the_full_scan_channel(harness) -> None:
    bot, events = harness
    from dataclasses import replace
    bot.settings = replace(bot.settings, hash_only_mode=True)
    run(bot, _message(1, FULL_SCAN))
    assert events["classified"] == []

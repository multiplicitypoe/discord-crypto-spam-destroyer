"""A known scam is acted on as soon as one image matches.

The handler used to download every image one after another, hash them all, and
only then delete. On a slow link a post of four 2 MB screenshots stayed up for
two to three seconds even though the first image alone was enough to act. These
tests pin the new order: the delete happens while slower images are still
downloading, an image whose hash fails still reaches the OpenAI scan, and the
parallel scan returns on the first confident verdict.
"""
import asyncio
import io
import random
from types import SimpleNamespace

import pytest
from PIL import Image

import discord_crypto_spam_destroyer.bot as bot_module
from discord_crypto_spam_destroyer.bot import CryptoSpamBot
from discord_crypto_spam_destroyer.config import load_settings
from discord_crypto_spam_destroyer.hashes.phash import compute_phash
from discord_crypto_spam_destroyer.hashes.store import FileHashStore
from discord_crypto_spam_destroyer.models import VisionIndicators, VisionResult
from discord_crypto_spam_destroyer.utils.image import DownloadedImage

FULL_SCAN = 1000


def _png(seed: int) -> bytes:
    rng = random.Random(seed)
    image = Image.new("RGB", (64, 64))
    image.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(64 * 64)])
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _message(seeds):
    attachments = [
        SimpleNamespace(content_type="image/png", filename=f"{s}.png", size=1000, url=f"https://cdn.test/{s}.png", seed=s)
        for s in seeds
    ]
    return SimpleNamespace(
        id=1571895260169113620,
        guild=SimpleNamespace(id=500),
        author=SimpleNamespace(bot=False, id=8, roles=[]),
        attachments=attachments,
        channel=SimpleNamespace(id=2000, parent_id=None, category_id=None, name="chat"),
    )


def _verdict(scam: bool, confidence: float) -> VisionResult:
    return VisionResult(is_crypto_scam=scam, confidence=confidence, reasons=["test"],
                        indicators=VisionIndicators(domains=[], amounts=[], wallet_addresses=[]))


@pytest.fixture
def harness(monkeypatch, tmp_path):
    for key in ("MULTI_SERVER_CONFIG_PATH", "FULL_SCAN_CHANNELS"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DISCORD_TOKEN", "t")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("MOD_CHANNEL", "1")
    monkeypatch.setenv("MOD_ROLE_ID", "2")
    bad = tmp_path / "bad_hashes.txt"
    bad.write_text(compute_phash(_png(1)) + "\n")
    monkeypatch.setenv("KNOWN_BAD_HASH_PATH", str(bad))

    bot = CryptoSpamBot.__new__(CryptoSpamBot)
    bot.settings = load_settings()
    bot.hash_store = FileHashStore(bad)
    bot._settings_cache = {}
    log: list[str] = []
    delays = {1: 0.0, 2: 0.3, 3: 0.3}

    async def read_attachment(attachment, max_bytes, timeout_s):
        await asyncio.sleep(delays.get(attachment.seed, 0.0))
        log.append(f"downloaded {attachment.seed}")
        return DownloadedImage(data=_png(attachment.seed), content_type="image/png",
                               filename=attachment.filename, url=attachment.url)

    async def delete(message):
        log.append("deleted")
        return True

    async def roles(guild, author):
        return "(test)"

    async def act(guild, author, **kwargs):
        log.append("softban")
        return "softban"

    async def classify(message_id, settings, downloaded):
        log.append(f"classified {len(downloaded)}")
        return _verdict(True, 0.95)

    monkeypatch.setattr(bot_module, "read_attachment", read_attachment)
    monkeypatch.setattr(bot_module, "safe_delete", delete)
    bot._classify_images = classify
    bot._format_author_roles = roles
    bot._apply_high_action_with_mod_check = act
    bot._report_allowed = lambda *a, **k: False
    return bot, log, delays


def test_the_post_is_deleted_before_the_slow_images_arrive(harness):
    bot, log, _ = harness
    asyncio.run(bot.on_message(_message([2, 1, 3])))
    assert log.index("deleted") < log.index("downloaded 2")
    assert log.index("deleted") < log.index("downloaded 3")
    assert log.count("deleted") == 1
    assert "softban" in log
    assert not any(entry.startswith("classified") for entry in log)


def test_a_post_with_no_known_image_still_goes_to_openai(harness):
    bot, log, _ = harness
    asyncio.run(bot.on_message(_message([4, 5, 6])))
    assert "classified 3" in log
    assert log.count("deleted") == 1


def test_an_image_that_cannot_be_hashed_is_still_scanned(harness, monkeypatch):
    bot, log, _ = harness
    monkeypatch.setattr(bot_module, "compute_phash_or_none", lambda data: None)
    asyncio.run(bot.on_message(_message([4, 5, 6])))
    assert "classified 3" in log


def test_a_hash_timeout_does_not_drop_the_post(harness, monkeypatch):
    bot, log, _ = harness
    monkeypatch.setattr(bot_module, "HASH_TIMEOUT_S", 0.01)

    def slow(data):
        import time
        time.sleep(0.1)
        return None

    monkeypatch.setattr(bot_module, "compute_phash_or_none", slow)
    asyncio.run(bot.on_message(_message([4, 5, 6])))
    assert "classified 3" in log


def test_parallel_scan_returns_on_the_first_confident_scam(monkeypatch):
    import time
    calls = []

    def classify_images(api_key, model, urls, detail, meta, debug):
        calls.append(urls[0])
        if urls[0] == "slow":
            time.sleep(1.0)
            return _verdict(False, 0.9)
        return _verdict(True, 0.97)

    monkeypatch.setattr(bot_module, "classify_images", classify_images)
    monkeypatch.setattr(bot_module, "to_data_url",
                        lambda image, dim: (image.url, 1, "image/png", 1, 1, None))
    bot = CryptoSpamBot.__new__(CryptoSpamBot)
    settings = SimpleNamespace(openai_api_key="k", parallel_image_classification=True,
                               openai_max_image_dim=512, openai_image_detail="low",
                               openai_model="m", debug_logs=False, confidence_high=0.85)
    images = [DownloadedImage(data=b"", content_type="image/png", filename="a", url=u) for u in ("slow", "fast")]

    async def timed():
        start = time.monotonic()
        result = await bot._classify_images(1, settings, images)
        return result, time.monotonic() - start

    # asyncio.run waits for the leftover thread when it shuts the loop down,
    # which the long-lived bot never does, so time it inside the loop.
    result, elapsed = asyncio.run(timed())
    assert result.is_crypto_scam
    assert elapsed < 0.9

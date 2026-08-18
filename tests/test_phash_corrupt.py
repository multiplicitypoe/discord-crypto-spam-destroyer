"""An image that cannot be decoded must not stop the others being scanned.

PIL raises SyntaxError for a broken PNG, which is neither OSError nor
ValueError, so it escaped the per image guard. Each attachment is now handled on
its own and a failure to decode one leaves the rest of the message to be checked
normally.
"""
import io

import pytest
from PIL import Image

from discord_crypto_spam_destroyer.hashes.phash import compute_phash, compute_phashes


def _valid_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (120, 30, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _corrupt_png() -> bytes:
    """A PNG whose first IDAT declares a short length.

    PIL then reads its next chunk header from the middle of the compressed
    stream, sees a garbage chunk id, and raises SyntaxError("broken PNG file").
    Corrupting chunk *data* instead gives a zlib OSError, which was already
    handled, so it has to be the chunk framing that breaks.
    """
    data = bytearray(_valid_png())
    i = data.find(b"IDAT")
    assert i > 0, "no IDAT chunk in generated png"
    length_at = i - 4
    declared = int.from_bytes(data[length_at:length_at + 4], "big")
    data[length_at:length_at + 4] = (max(declared - 24, 1)).to_bytes(4, "big")
    return bytes(data)


def test_a_corrupt_image_is_skipped_not_raised() -> None:
    with pytest.raises(Exception):
        compute_phash(_corrupt_png())          # the raw helper may still raise
    assert compute_phashes([_corrupt_png()]) == []   # the batch helper must not


def test_a_good_image_still_hashes() -> None:
    hashes = compute_phashes([_valid_png()])
    assert len(hashes) == 1
    assert hashes[0]


def test_one_corrupt_image_does_not_lose_the_others() -> None:
    """A bad image must not discard its siblings in the same message."""
    hashes = compute_phashes([_corrupt_png(), _valid_png(), _corrupt_png()])
    assert len(hashes) == 1, "the valid image must still be scanned"

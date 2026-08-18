"""A uniform image must never be able to poison the denylist.

pHash sets a bit per DCT coefficient above the median, so a normal image lands
near 32 bits set. A uniform image collapses to almost none, and a hash like that
matches unrelated images rather than the one it came from.

Such hashes are refused when added and ignored when matching, on both sides, so
an entry already on the list cannot fire either.
"""
import io

from PIL import Image

from discord_crypto_spam_destroyer.hashes.phash import compute_phash
from discord_crypto_spam_destroyer.hashes.store import (
    FileHashStore,
    is_degenerate_phash,
    match_hashes,
)

BLANK_WHITE = "8000000000000000"
BLANK_BLACK = "0000000000000000"
REAL = "c1e1e3c65c5e5c94"          # taken from a genuine denylist entry


def _png(colour) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (256, 256), colour).save(buf, format="PNG")
    return buf.getvalue()


def test_a_blank_white_image_really_does_hash_to_the_poisoned_value() -> None:
    assert compute_phash(_png((255, 255, 255))) == BLANK_WHITE


def test_uniform_image_hashes_are_flagged_degenerate() -> None:
    assert is_degenerate_phash(BLANK_WHITE)
    assert is_degenerate_phash(BLANK_BLACK)
    assert is_degenerate_phash(compute_phash(_png((0, 0, 0))))


def test_a_real_hash_is_not_flagged() -> None:
    assert not is_degenerate_phash(REAL)


def test_matching_ignores_a_poisoned_denylist_entry() -> None:
    """Even if the bad value is already on disk, it must not match anything."""
    result = match_hashes([BLANK_WHITE], {BLANK_WHITE, REAL})
    assert result.matched is False
    assert result.matched_hashes == []


def test_matching_still_works_for_real_hashes() -> None:
    result = match_hashes([REAL], {BLANK_WHITE, REAL})
    assert result.matched is True
    assert result.matched_hashes == [REAL]


def test_a_blank_image_cannot_be_added_to_the_denylist(tmp_path) -> None:
    store = FileHashStore(path=tmp_path / "bad_hashes.txt")
    store.add(REAL)
    store.add(BLANK_WHITE)
    assert store.load() == {REAL}, "the blank hash must be refused"

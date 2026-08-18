from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from discord_crypto_spam_destroyer.models import HashMatch

# pHash sets one bit per DCT coefficient above the median, so a normal image
# lands near 32 bits set out of 64. A uniform image collapses to almost none:
# pure white is 8000000000000000 and pure black is 0000000000000000. Such a
# hash matches every faint or mostly blank image, so it must never sit on the
# denylist. One did, and it deleted and softbanned two innocent users before it
# was spotted.
_MIN_BITS = 5
_MAX_BITS = 59


def is_degenerate_phash(phash: str) -> bool:
    """True if this hash positively represents a near uniform image.

    Anything that is not a 64 bit hex digest returns False rather than True:
    if we cannot assess a value we leave existing behaviour alone instead of
    silently refusing to match it.
    """
    value = (phash or "").strip()
    if len(value) != 16:
        return False
    try:
        bits = bin(int(value, 16)).count("1")
    except ValueError:
        return False
    return bits < _MIN_BITS or bits > _MAX_BITS


class HashStore:
    def load(self) -> set[str]:
        raise NotImplementedError

    def add(self, phash: str) -> None:
        raise NotImplementedError


@dataclass
class FileHashStore(HashStore):
    path: Path

    def load(self) -> set[str]:
        if not self.path.exists():
            return set()
        content = self.path.read_text(encoding="utf-8")
        return {line.strip() for line in content.splitlines() if line.strip()}

    def add(self, phash: str) -> None:
        if is_degenerate_phash(phash):
            # Refused rather than raised: a moderator pressing "Add hashes" on a
            # message that happens to contain a blank image should not poison the
            # denylist, and should not see an error either.
            return
        existing = self.load()
        if phash in existing:
            return
        existing.add(phash)
        sorted_hashes = sorted(existing)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(sorted_hashes) + "\n", encoding="utf-8")


def match_hashes(candidates: Iterable[str], known_bad: set[str]) -> HashMatch:
    # Degenerate hashes are ignored on both sides, so an entry already on disk
    # from before this guard existed still cannot cause a false positive.
    candidates = list(candidates)
    matches = [
        phash
        for phash in candidates
        if phash in known_bad and not is_degenerate_phash(phash)
    ]
    # What is left is what a moderator can usefully add. Degenerate hashes are
    # excluded because the store refuses them, so offering them would mislead.
    unmatched = []
    seen = set()
    for phash in candidates:
        if phash in known_bad or is_degenerate_phash(phash) or phash in seen:
            continue
        seen.add(phash)
        unmatched.append(phash)
    return HashMatch(
        matched=bool(matches),
        matched_hashes=matches,
        unmatched_hashes=unmatched,
    )

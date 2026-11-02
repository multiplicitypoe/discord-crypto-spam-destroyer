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


def _read_hashes(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()
    content = path.read_text(encoding="utf-8")
    return {line.strip() for line in content.splitlines() if line.strip()}


def _write_hashes(path: Path, hashes: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{phash}\n" for phash in sorted(hashes)), encoding="utf-8")


@dataclass
class FileHashStore(HashStore):
    """The denylist: a local list this bot writes plus an optional default list.

    The default list ships with the repository and is replaced when you pull.
    The local list is untracked and holds whatever moderators add, so pulling a
    newer default list never conflicts with it. Matching uses both.
    """

    path: Path
    default_path: Path | None = None

    def load(self) -> set[str]:
        return _read_hashes(self.default_path) | _read_hashes(self.path)

    def add(self, phash: str) -> None:
        if is_degenerate_phash(phash):
            # Refused rather than raised: a moderator pressing "Add hashes" on a
            # message that happens to contain a blank image should not poison the
            # denylist, and should not see an error either.
            return
        if phash in self.load():
            return
        _write_hashes(self.path, _read_hashes(self.path) | {phash})

    def promote(self) -> int:
        """Move the local list into the default list and return how many were new.

        For whoever maintains the repository: run it, then commit the default list.
        """
        if self.default_path is None:
            raise ValueError("there is no default list to promote into")
        local = _read_hashes(self.path)
        default = _read_hashes(self.default_path)
        new = {phash for phash in local if not is_degenerate_phash(phash)} - default
        if new:
            _write_hashes(self.default_path, default | new)
        _write_hashes(self.path, _read_hashes(self.path) - local)
        return len(new)


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

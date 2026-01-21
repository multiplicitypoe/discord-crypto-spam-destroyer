from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from discord_crypto_spam_destroyer.models import HashMatch


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
        existing = self.load()
        if phash in existing:
            return
        existing.add(phash)
        sorted_hashes = sorted(existing)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(sorted_hashes) + "\n", encoding="utf-8")


def match_hashes(candidates: Iterable[str], known_bad: set[str]) -> HashMatch:
    matches = [phash for phash in candidates if phash in known_bad]
    return HashMatch(matched=bool(matches), matched_hashes=matches)

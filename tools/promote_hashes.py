from __future__ import annotations

import os
from pathlib import Path

from discord_crypto_spam_destroyer.hashes.store import FileHashStore


def main() -> None:
    store = FileHashStore(
        Path(os.getenv("KNOWN_BAD_HASH_PATH", "data/bad_hashes.txt")),
        Path(os.getenv("DEFAULT_BAD_HASH_PATH", "data/default_bad_hashes.txt")),
    )
    promoted = store.promote()
    print(f"Moved {promoted} new hashes into {store.default_path}. Commit that file to ship them.")


if __name__ == "__main__":
    main()

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image
import imagehash


def generate_hashes(image_dir: Path) -> set[str]:
    hashes: set[str] = set()
    for path in sorted(image_dir.glob("*.webp")):
        if not path.is_file():
            continue
        with Image.open(BytesIO(path.read_bytes())) as image:
            hashes.add(str(imagehash.phash(image)))
    return hashes


def load_existing_hashes(path: Path) -> set[str]:
    if not path.exists():
        return set()
    content = path.read_text(encoding="utf-8")
    return {line.strip() for line in content.splitlines() if line.strip()}


def main() -> None:
    image_dir = Path("data/known_bad_scam_images")
    output_path = Path("data/bad_hashes.txt")
    hashes = generate_hashes(image_dir)
    existing = load_existing_hashes(output_path)
    merged = sorted(existing | hashes)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(merged) + "\n", encoding="utf-8")
    added = len(merged) - len(existing)
    print(
        f"Wrote {len(merged)} hashes to {output_path} ({added} new from images, {len(existing)} existing)"
    )


if __name__ == "__main__":
    main()

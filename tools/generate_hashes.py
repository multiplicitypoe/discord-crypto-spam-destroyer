from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image
import imagehash


def generate_hashes(image_dir: Path) -> list[str]:
    hashes = []
    for path in sorted(image_dir.glob("*.webp")):
        if not path.is_file():
            continue
        with Image.open(BytesIO(path.read_bytes())) as image:
            hashes.append(str(imagehash.phash(image)))
    return sorted(set(hashes))


def main() -> None:
    image_dir = Path("data/known_bad_scam_images")
    output_path = Path("data/bad_hashes.txt")
    hashes = generate_hashes(image_dir)
    output_path.write_text("\n".join(hashes) + "\n", encoding="utf-8")
    print(f"Wrote {len(hashes)} hashes to {output_path}")


if __name__ == "__main__":
    main()

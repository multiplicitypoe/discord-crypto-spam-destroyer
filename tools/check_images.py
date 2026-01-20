from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    from discord_crypto_spam_destroyer.vision.openai_client import classify_images
    from discord_crypto_spam_destroyer.utils.image import DownloadedImage, to_data_url
except ModuleNotFoundError:
    sys.path.append(str(Path("src").resolve()))
    from discord_crypto_spam_destroyer.vision.openai_client import classify_images
    from discord_crypto_spam_destroyer.utils.image import DownloadedImage, to_data_url


def load_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return api_key
    key_path = Path("OPENAI_KEY.txt")
    if key_path.exists():
        return key_path.read_text(encoding="utf-8").strip()
    raise SystemExit("OPENAI_API_KEY not set and OPENAI_KEY.txt not found")


def iter_images(limit: int) -> list[Path]:
    image_dir = Path("data/known_bad_scam_images")
    images = [p for p in sorted(image_dir.glob("*.webp")) if p.is_file()]
    return images[:limit]


def main() -> None:
    api_key = load_api_key()
    max_images = int(os.getenv("MAX_IMAGES", "3"))
    images = iter_images(max_images)
    if not images:
        raise SystemExit("No images found in data/known_bad_scam_images")

    for path in images:
        image = DownloadedImage(
            data=path.read_bytes(),
            content_type="image/webp",
            filename=path.name,
            url=str(path),
        )
        try:
            result = classify_images(api_key, "gpt-4o-mini", [to_data_url(image)])
        except Exception as exc:
            print(f"{path.name}: ERROR {type(exc).__name__}: {exc}")
            continue
        verdict = "SCAM" if result.is_crypto_scam else "not_scam"
        reasons = ", ".join(result.reasons) if result.reasons else "none"
        print(f"{path.name}: {verdict} (confidence={result.confidence:.2f})")
        print(f"  reasons: {reasons}")
        if result.indicators.domains or result.indicators.amounts or result.indicators.wallet_addresses:
            print(
                "  indicators:",
                "domains=", ", ".join(map(str, result.indicators.domains)) or "none",
                "amounts=", ", ".join(map(str, result.indicators.amounts)) or "none",
                "wallets=", ", ".join(map(str, result.indicators.wallet_addresses)) or "none",
            )


if __name__ == "__main__":
    main()

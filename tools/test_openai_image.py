from __future__ import annotations

import os
from pathlib import Path

from discord_crypto_spam_destroyer.vision.openai_client import classify_images
from discord_crypto_spam_destroyer.utils.image import DownloadedImage, to_data_url


def main() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY not set")

    image_path = Path("data/known_bad_scam_images/2.webp")
    image = DownloadedImage(
        data=image_path.read_bytes(),
        content_type="image/webp",
        filename=image_path.name,
        url=str(image_path),
    )
    result = classify_images(api_key, "gpt-4o-mini", [to_data_url(image)])
    print(result)


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
from typing import Sequence

from openai import OpenAI

from discord_crypto_spam_destroyer.models import VisionIndicators, VisionResult

SYSTEM_PROMPT = (
    "You are a moderation classifier for Discord image spam. "
    "Return JSON only with keys: is_crypto_scam (bool), confidence (0-1), "
    "reasons (array of short strings), indicators (object with domains, amounts, "
    "wallet_addresses). Be concise and factual."
)


def build_vision_request(
    images_base64: Sequence[str],
    image_detail: str,
) -> list[dict[str, object]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Classify these images."},
                *[
                    {
                        "type": "image_url",
                        "image_url": {"url": image_data, "detail": image_detail},
                    }
                    for image_data in images_base64
                ],
            ],
        },
    ]


def parse_vision_response(raw_content: str) -> VisionResult:
    payload = json.loads(raw_content)
    indicators = payload.get("indicators") or {}
    return VisionResult(
        is_crypto_scam=bool(payload.get("is_crypto_scam")),
        confidence=float(payload.get("confidence", 0.0)),
        reasons=list(payload.get("reasons") or []),
        indicators=VisionIndicators(
            domains=list(indicators.get("domains") or []),
            amounts=list(indicators.get("amounts") or []),
            wallet_addresses=list(indicators.get("wallet_addresses") or []),
        ),
    )


def classify_images(
    api_key: str,
    model: str,
    images_base64: Sequence[str],
    image_detail: str,
) -> VisionResult:
    client = OpenAI(api_key=api_key)
    messages = build_vision_request(images_base64, image_detail)
    response = client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        response_format={"type": "json_object"},
        temperature=0,
    )
    content = response.choices[0].message.content or "{}"
    return parse_vision_response(content)

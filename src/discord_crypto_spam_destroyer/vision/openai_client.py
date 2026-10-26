from __future__ import annotations

import json
import logging
import os
from typing import Sequence

from openai import OpenAI

from discord_crypto_spam_destroyer.models import VisionIndicators, VisionResult

logger = logging.getLogger("discord_crypto_spam_destroyer")

SYSTEM_PROMPT = """You review images posted in a Path of Exile Discord server. Bots and hacked accounts spam crypto scams there, usually as a set of up to 4 images and sometimes as a single image. Most of these scams promote an online crypto casino or betting site, or fake trading and investment profits. You see one image at a time. Decide whether this image is part of one of those scam posts.

Treat an image as part of a scam when it shows any of these:
- An online casino, gambling, betting or crypto gambling site: account or profile pages, VIP, rakeback or bonus screens, promo or bonus codes, deposit and withdraw pages, game lobbies, win screenshots.
- A withdrawal, payout or transfer success screen, receipt, or blockchain transaction detail (USDT, BTC, ETH and similar), especially with a large amount.
- A crypto exchange, wallet, trading app or bank screenshot with large balances, deposits, withdrawals or profit figures (Binance, Coinbase, Bybit, Trust Wallet, Kraken, MetaMask and similar).
- A crypto trading performance or profit recap (profit and loss, win rate, return percentage, balance growth), even with no pitch or contact details.
- A screenshot of a tweet, X post, Telegram, WhatsApp or other chat that promotes trading, investing, signals, mentorship, giveaways, airdrops, passive income or guaranteed returns, or that tells people to message someone.
- A named handle (@name), phone number, link, referral code or QR code inviting people to join or contact someone about making money.
- Proof of profit imagery: stacks of cash, luxury cars, watches, or lifestyle photos presented as winnings or trading results, or text like "turned $500 into $10,000".
- Fake news or endorsement graphics about crypto, investing or gambling.

Not a scam: Path of Exile and other game screenshots (including in-game shops, trade windows, currency and item prices), builds, skill trees, memes, ordinary photos and social posts, normal chat, sports or news with no investment or gambling pitch, a purchase receipt for a game or subscription, and a chart or crypto mention that is not soliciting anyone.

Return JSON only with keys: is_crypto_scam (bool), confidence (0 to 1), reasons (array of at most 3 strings, 8 words each), indicators (object with arrays domains, amounts, wallet_addresses). Use confidence 0.85 or higher only when the image clearly matches the scam list above. Use below 0.5 when it does not."""


def completion_options(model: str) -> dict[str, object]:
    """Request parameters that differ by model family.

    gpt-4.x models take a temperature. gpt-5 and gpt-6 models take a reasoning
    effort, which defaults to none and can be changed with OPENAI_REASONING_EFFORT.
    """
    if model.startswith(("gpt-4", "chatgpt-4")):
        return {"temperature": 0}
    return {"reasoning_effort": os.getenv("OPENAI_REASONING_EFFORT", "none")}


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
    image_meta: list[dict[str, object]] | None = None,
    debug_logs: bool = False,
) -> VisionResult:
    client = OpenAI(api_key=api_key)
    messages = build_vision_request(images_base64, image_detail)
    response = client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type,assignment]
        response_format={"type": "json_object"},
        **completion_options(model),  # type: ignore[arg-type]
    )
    if debug_logs:
        usage = response.usage
        logger.info(
            "OpenAI usage model=%s request_id=%s detail=%s n_images=%s img_meta=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s",
            model,
            response.id,
            image_detail,
            len(images_base64),
            image_meta,
            getattr(usage, "prompt_tokens", None),
            getattr(usage, "completion_tokens", None),
            getattr(usage, "total_tokens", None),
        )
    content = response.choices[0].message.content or "{}"
    return parse_vision_response(content)

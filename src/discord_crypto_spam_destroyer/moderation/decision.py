from __future__ import annotations

from discord_crypto_spam_destroyer.models import ConfidenceBand, Decision, VisionResult


def confidence_band(confidence: float, high: float, medium: float) -> ConfidenceBand:
    if confidence >= high:
        return ConfidenceBand.HIGH
    if confidence >= medium:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.LOW


def decision_from_result(
    result: VisionResult,
    high_threshold: float,
    medium_threshold: float,
) -> Decision:
    if not result.is_crypto_scam:
        return Decision(is_scam=False, confidence_band=ConfidenceBand.LOW, reason="model_not_scam")

    band = confidence_band(result.confidence, high_threshold, medium_threshold)
    if band == ConfidenceBand.LOW:
        return Decision(is_scam=False, confidence_band=band, reason="model_low_confidence")

    reason = "model_high_confidence" if band == ConfidenceBand.HIGH else "model_medium_confidence"
    return Decision(is_scam=True, confidence_band=band, reason=reason)

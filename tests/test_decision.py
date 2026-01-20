from discord_crypto_spam_destroyer.moderation.decision import confidence_band, decision_from_result
from discord_crypto_spam_destroyer.models import ConfidenceBand, VisionIndicators, VisionResult


def test_confidence_band_thresholds() -> None:
    assert confidence_band(0.9, 0.85, 0.65) == ConfidenceBand.HIGH
    assert confidence_band(0.7, 0.85, 0.65) == ConfidenceBand.MEDIUM
    assert confidence_band(0.4, 0.85, 0.65) == ConfidenceBand.LOW


def test_decision_flow_non_scam() -> None:
    result = VisionResult(
        is_crypto_scam=False,
        confidence=0.9,
        reasons=["no scam"],
        indicators=VisionIndicators(domains=[], amounts=[], wallet_addresses=[]),
    )
    decision = decision_from_result(result, 0.85, 0.65)
    assert decision.is_scam is False
    assert decision.confidence_band == ConfidenceBand.LOW


def test_decision_flow_high_confidence() -> None:
    result = VisionResult(
        is_crypto_scam=True,
        confidence=0.9,
        reasons=["scam"],
        indicators=VisionIndicators(domains=[], amounts=[], wallet_addresses=[]),
    )
    decision = decision_from_result(result, 0.85, 0.65)
    assert decision.is_scam is True
    assert decision.confidence_band == ConfidenceBand.HIGH


def test_decision_flow_medium_confidence() -> None:
    result = VisionResult(
        is_crypto_scam=True,
        confidence=0.7,
        reasons=["scam"],
        indicators=VisionIndicators(domains=[], amounts=[], wallet_addresses=[]),
    )
    decision = decision_from_result(result, 0.85, 0.65)
    assert decision.is_scam is True
    assert decision.confidence_band == ConfidenceBand.MEDIUM

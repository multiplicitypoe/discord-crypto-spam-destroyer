from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class ConfidenceBand(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class VisionIndicators:
    domains: Sequence[str]
    amounts: Sequence[str]
    wallet_addresses: Sequence[str]


@dataclass(frozen=True)
class VisionResult:
    is_crypto_scam: bool
    confidence: float
    reasons: Sequence[str]
    indicators: VisionIndicators


@dataclass(frozen=True)
class Decision:
    is_scam: bool
    confidence_band: ConfidenceBand
    reason: str


@dataclass(frozen=True)
class HashMatch:
    matched: bool
    matched_hashes: Sequence[str]

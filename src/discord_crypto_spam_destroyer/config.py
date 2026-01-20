from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, cast

ActionHigh = Literal["kick", "ban", "softban", "report_only"]
ActionMedium = Literal["delete_and_report", "delete_only"]


@dataclass(frozen=True)
class Settings:
    discord_token: str
    openai_api_key: str | None
    openai_model: str
    min_image_count: int
    max_images_to_analyze: int
    known_bad_hash_path: str
    action_high: ActionHigh
    action_medium: ActionMedium
    confidence_high: float
    confidence_medium: float
    mod_channel: str | None
    mod_role_id: int | None
    report_high: bool
    report_cooldown_s: float
    hash_only_mode: bool
    debug_logs: bool
    download_timeout_s: float
    max_image_bytes: int


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value


def _env_optional(name: str) -> str | None:
    return os.getenv(name)


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    return float(value)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    discord_token = _env_optional("DISCORD_TOKEN")
    openai_api_key = _env_optional("OPENAI_API_KEY")
    if not discord_token:
        raise ValueError("DISCORD_TOKEN is required")

    action_high = _env("ACTION_HIGH", "kick")
    if action_high not in {"kick", "ban", "softban", "report_only"}:
        raise ValueError("ACTION_HIGH must be 'kick', 'ban', 'softban', or 'report_only'")

    action_medium = _env("ACTION_MEDIUM", "delete_and_report")
    if action_medium not in {"delete_and_report", "delete_only"}:
        raise ValueError("ACTION_MEDIUM must be 'delete_and_report' or 'delete_only'")

    mod_role_value = _env_optional("MOD_ROLE_ID")

    if not _env_optional("MOD_CHANNEL"):
        raise ValueError("MOD_CHANNEL is required")

    return Settings(
        discord_token=discord_token,
        openai_api_key=openai_api_key,
        openai_model=_env("OPENAI_MODEL", "gpt-4o-mini"),
        min_image_count=_env_int("MIN_IMAGE_COUNT", 3),
        max_images_to_analyze=_env_int("MAX_IMAGES_TO_ANALYZE", 4),
        known_bad_hash_path=_env("KNOWN_BAD_HASH_PATH", "data/bad_hashes.txt"),
        action_high=cast(ActionHigh, action_high),
        action_medium=cast(ActionMedium, action_medium),
        confidence_high=_env_float("CONFIDENCE_HIGH", 0.85),
        confidence_medium=_env_float("CONFIDENCE_MEDIUM", 0.65),
        mod_channel=_env_optional("MOD_CHANNEL"),
        mod_role_id=int(mod_role_value) if mod_role_value else None,
        report_high=_env_bool("REPORT_HIGH", True),
        report_cooldown_s=_env_float("REPORT_COOLDOWN_S", 20.0),
        hash_only_mode=_env_bool("HASH_ONLY_MODE", False),
        debug_logs=_env_bool("DEBUG_LOGS", False),
        download_timeout_s=_env_float("DOWNLOAD_TIMEOUT_S", 8.0),
        max_image_bytes=_env_int("MAX_IMAGE_BYTES", 5_000_000),
    )

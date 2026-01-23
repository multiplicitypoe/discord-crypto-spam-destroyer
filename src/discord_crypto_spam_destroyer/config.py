from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

ActionHigh = Literal["kick", "ban", "softban", "report_only"]
ActionMedium = Literal["delete_and_report", "delete_only"]

UNSET = object()

MULTI_SERVER_ALLOWED_KEYS = {
    "openai_api_key",
    "openai_model",
    "min_image_count",
    "max_images_to_analyze",
    "action_high",
    "action_medium",
    "confidence_high",
    "confidence_medium",
    "mod_channel",
    "mod_role_id",
    "report_high",
    "report_cooldown_s",
    "message_processing_delay_s",
    "softban_delete_days",
    "hash_only_mode",
    "debug_logs",
    "download_timeout_s",
    "max_image_bytes",
}


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
    report_store_ttl_hours: int
    message_processing_delay_s: float
    softban_delete_days: int
    hash_only_mode: bool
    debug_logs: bool
    download_timeout_s: float
    max_image_bytes: int
    multi_server_config_path: str | None
    multi_server_config: dict[int, "SettingsOverrides"]


@dataclass(frozen=True)
class ResolvedSettings:
    discord_token: str
    openai_api_key: str | None
    openai_model: str
    min_image_count: int
    max_images_to_analyze: int
    action_high: ActionHigh
    action_medium: ActionMedium
    confidence_high: float
    confidence_medium: float
    mod_channel: str | None
    mod_role_id: int | None
    report_high: bool
    report_cooldown_s: float
    message_processing_delay_s: float
    softban_delete_days: int
    hash_only_mode: bool
    debug_logs: bool
    download_timeout_s: float
    max_image_bytes: int


@dataclass(frozen=True)
class SettingsOverrides:
    openai_api_key: str | None | object = UNSET
    openai_model: str | None | object = UNSET
    min_image_count: int | None | object = UNSET
    max_images_to_analyze: int | None | object = UNSET
    action_high: ActionHigh | None | object = UNSET
    action_medium: ActionMedium | None | object = UNSET
    confidence_high: float | None | object = UNSET
    confidence_medium: float | None | object = UNSET
    mod_channel: str | None | object = UNSET
    mod_role_id: int | None | object = UNSET
    report_high: bool | None | object = UNSET
    report_cooldown_s: float | None | object = UNSET
    message_processing_delay_s: float | None | object = UNSET
    softban_delete_days: int | None | object = UNSET
    hash_only_mode: bool | None | object = UNSET
    debug_logs: bool | None | object = UNSET
    download_timeout_s: float | None | object = UNSET
    max_image_bytes: int | None | object = UNSET


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


def _parse_action_high(value: str) -> ActionHigh:
    if value not in {"kick", "ban", "softban", "report_only"}:
        raise ValueError("ACTION_HIGH must be 'kick', 'ban', 'softban', or 'report_only'")
    return cast(ActionHigh, value)


def _parse_action_medium(value: str) -> ActionMedium:
    if value not in {"delete_and_report", "delete_only"}:
        raise ValueError("ACTION_MEDIUM must be 'delete_and_report' or 'delete_only'")
    return cast(ActionMedium, value)


def _parse_multi_server_overrides(payload: dict[str, Any]) -> SettingsOverrides:
    if "action_high" in payload and not isinstance(payload["action_high"], str):
        raise ValueError("action_high must be a string")
    if "action_medium" in payload and not isinstance(payload["action_medium"], str):
        raise ValueError("action_medium must be a string")
    return SettingsOverrides(
        openai_api_key=_as_optional_str(payload.get("openai_api_key", UNSET)),
        openai_model=_as_optional_str(payload.get("openai_model", UNSET)),
        min_image_count=_as_optional_int(payload.get("min_image_count", UNSET)),
        max_images_to_analyze=_as_optional_int(payload.get("max_images_to_analyze", UNSET)),
        action_high=_as_optional_action_high(payload.get("action_high", UNSET)),
        action_medium=_as_optional_action_medium(payload.get("action_medium", UNSET)),
        confidence_high=_as_optional_float(payload.get("confidence_high", UNSET)),
        confidence_medium=_as_optional_float(payload.get("confidence_medium", UNSET)),
        mod_channel=_as_optional_str(payload.get("mod_channel", UNSET)),
        mod_role_id=_as_optional_int(payload.get("mod_role_id", UNSET)),
        report_high=_as_optional_bool(payload.get("report_high", UNSET)),
        report_cooldown_s=_as_optional_float(payload.get("report_cooldown_s", UNSET)),
        message_processing_delay_s=_as_optional_float(payload.get("message_processing_delay_s", UNSET)),
        softban_delete_days=_as_optional_int(payload.get("softban_delete_days", UNSET)),
        hash_only_mode=_as_optional_bool(payload.get("hash_only_mode", UNSET)),
        debug_logs=_as_optional_bool(payload.get("debug_logs", UNSET)),
        download_timeout_s=_as_optional_float(payload.get("download_timeout_s", UNSET)),
        max_image_bytes=_as_optional_int(payload.get("max_image_bytes", UNSET)),
    )


def _as_optional_str(value: Any) -> str | None | object:
    if value is UNSET:
        return UNSET
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _as_optional_int(value: Any) -> int | None | object:
    if value is UNSET:
        return UNSET
    if value is None:
        return None
    return int(value)


def _as_optional_float(value: Any) -> float | None | object:
    if value is UNSET:
        return UNSET
    if value is None:
        return None
    return float(value)


def _as_optional_bool(value: Any) -> bool | None | object:
    if value is UNSET:
        return UNSET
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _as_optional_action_high(value: Any) -> ActionHigh | None | object:
    if value is UNSET:
        return UNSET
    if value is None:
        return None
    return _parse_action_high(str(value))


def _as_optional_action_medium(value: Any) -> ActionMedium | None | object:
    if value is UNSET:
        return UNSET
    if value is None:
        return None
    return _parse_action_medium(str(value))


def _load_multi_server_config(path: str | None) -> dict[int, SettingsOverrides]:
    if not path:
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("MULTI_SERVER_CONFIG_PATH must point to a JSON object")
    config: dict[int, SettingsOverrides] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not key.isdigit():
            raise ValueError("Guild ids in multi server config must be string numbers")
        if not isinstance(value, dict):
            raise ValueError(f"Config for guild {key} must be an object")
        unknown_keys = sorted(set(value.keys()) - MULTI_SERVER_ALLOWED_KEYS)
        if unknown_keys:
            raise ValueError(
                f"Unknown keys in multi server config for guild {key}: {', '.join(unknown_keys)}"
            )
        config[int(key)] = _parse_multi_server_overrides(value)
    return config


def _resolve_value(override: Any | object, fallback: Any) -> Any:
    return fallback if override is UNSET else override


def _resolve_required(name: str, override: Any | object, fallback: Any) -> Any:
    if override is UNSET:
        return fallback
    if override is None:
        raise ValueError(f"{name} cannot be null")
    return override


def resolve_settings(base: Settings, guild_id: int) -> ResolvedSettings:
    overrides = base.multi_server_config.get(guild_id)
    if not overrides:
        return ResolvedSettings(
            discord_token=base.discord_token,
            openai_api_key=base.openai_api_key,
            openai_model=base.openai_model,
            min_image_count=base.min_image_count,
            max_images_to_analyze=base.max_images_to_analyze,
            action_high=base.action_high,
            action_medium=base.action_medium,
            confidence_high=base.confidence_high,
            confidence_medium=base.confidence_medium,
            mod_channel=base.mod_channel,
            mod_role_id=base.mod_role_id,
            report_high=base.report_high,
            report_cooldown_s=base.report_cooldown_s,
            message_processing_delay_s=base.message_processing_delay_s,
            softban_delete_days=base.softban_delete_days,
            hash_only_mode=base.hash_only_mode,
            debug_logs=base.debug_logs,
            download_timeout_s=base.download_timeout_s,
            max_image_bytes=base.max_image_bytes,
        )

    action_high = base.action_high
    if overrides.action_high is not UNSET:
        action_high = cast(ActionHigh, _resolve_required("action_high", overrides.action_high, base.action_high))

    action_medium = base.action_medium
    if overrides.action_medium is not UNSET:
        action_medium = cast(ActionMedium, _resolve_required("action_medium", overrides.action_medium, base.action_medium))

    return ResolvedSettings(
        discord_token=base.discord_token,
        openai_api_key=_resolve_value(overrides.openai_api_key, base.openai_api_key),
        openai_model=_resolve_required("openai_model", overrides.openai_model, base.openai_model),
        min_image_count=_resolve_required("min_image_count", overrides.min_image_count, base.min_image_count),
        max_images_to_analyze=_resolve_required(
            "max_images_to_analyze",
            overrides.max_images_to_analyze,
            base.max_images_to_analyze,
        ),
        action_high=action_high,
        action_medium=action_medium,
        confidence_high=_resolve_required(
            "confidence_high",
            overrides.confidence_high,
            base.confidence_high,
        ),
        confidence_medium=_resolve_required(
            "confidence_medium",
            overrides.confidence_medium,
            base.confidence_medium,
        ),
        mod_channel=_resolve_required("mod_channel", overrides.mod_channel, base.mod_channel),
        mod_role_id=_resolve_required("mod_role_id", overrides.mod_role_id, base.mod_role_id),
        report_high=_resolve_required("report_high", overrides.report_high, base.report_high),
        report_cooldown_s=_resolve_required(
            "report_cooldown_s",
            overrides.report_cooldown_s,
            base.report_cooldown_s,
        ),
        message_processing_delay_s=_resolve_required(
            "message_processing_delay_s",
            overrides.message_processing_delay_s,
            base.message_processing_delay_s,
        ),
        softban_delete_days=_resolve_required(
            "softban_delete_days",
            overrides.softban_delete_days,
            base.softban_delete_days,
        ),
        hash_only_mode=_resolve_required("hash_only_mode", overrides.hash_only_mode, base.hash_only_mode),
        debug_logs=_resolve_required("debug_logs", overrides.debug_logs, base.debug_logs),
        download_timeout_s=_resolve_required(
            "download_timeout_s",
            overrides.download_timeout_s,
            base.download_timeout_s,
        ),
        max_image_bytes=_resolve_required(
            "max_image_bytes",
            overrides.max_image_bytes,
            base.max_image_bytes,
        ),
    )


def load_settings() -> Settings:
    discord_token = _env_optional("DISCORD_TOKEN")
    openai_api_key = _env_optional("OPENAI_API_KEY")
    if not discord_token:
        raise ValueError("DISCORD_TOKEN is required")

    multi_server_config_path = _env_optional("MULTI_SERVER_CONFIG_PATH")

    action_high = _parse_action_high(_env("ACTION_HIGH", "softban"))
    action_medium = _parse_action_medium(_env("ACTION_MEDIUM", "delete_and_report"))

    mod_role_value = _env_optional("MOD_ROLE_ID")

    if not multi_server_config_path and not _env_optional("MOD_CHANNEL"):
        raise ValueError("MOD_CHANNEL is required")
    if not multi_server_config_path and not mod_role_value:
        raise ValueError("MOD_ROLE_ID is required")

    multi_server_config = _load_multi_server_config(multi_server_config_path)

    return Settings(
        discord_token=discord_token,
        openai_api_key=openai_api_key,
        openai_model=_env("OPENAI_MODEL", "gpt-4o-mini"),
        min_image_count=_env_int("MIN_IMAGE_COUNT", 3),
        max_images_to_analyze=_env_int("MAX_IMAGES_TO_ANALYZE", 4),
        known_bad_hash_path=_env("KNOWN_BAD_HASH_PATH", "data/bad_hashes.txt"),
        action_high=action_high,
        action_medium=action_medium,
        confidence_high=_env_float("CONFIDENCE_HIGH", 0.85),
        confidence_medium=_env_float("CONFIDENCE_MEDIUM", 0.65),
        mod_channel=_env_optional("MOD_CHANNEL"),
        mod_role_id=int(mod_role_value) if mod_role_value else None,
        report_high=_env_bool("REPORT_HIGH", True),
        report_cooldown_s=_env_float("REPORT_COOLDOWN_S", 20.0),
        report_store_ttl_hours=_env_int("REPORT_STORE_TTL_HOURS", 24),
        message_processing_delay_s=_env_float("MESSAGE_PROCESSING_DELAY_S", 0.0),
        softban_delete_days=_env_int("SOFTBAN_DELETE_DAYS", 1),
        hash_only_mode=_env_bool("HASH_ONLY_MODE", False),
        debug_logs=_env_bool("DEBUG_LOGS", False),
        download_timeout_s=_env_float("DOWNLOAD_TIMEOUT_S", 8.0),
        max_image_bytes=_env_int("MAX_IMAGE_BYTES", 5_000_000),
        multi_server_config_path=multi_server_config_path,
        multi_server_config=multi_server_config,
    )

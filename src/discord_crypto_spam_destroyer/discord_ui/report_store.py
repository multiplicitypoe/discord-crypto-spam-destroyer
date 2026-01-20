from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ReportRecord:
    message_id: int
    channel_id: int
    guild_id: int
    author_id: int
    mod_role_id: int | None
    allow_hash_add: bool
    kick_disabled: bool
    all_hashes: list[str]
    created_at: float


class ReportStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load_reports(self) -> list[ReportRecord]:
        if not self._path.exists():
            return []
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        records = []
        for item in payload.get("reports", []):
            records.append(
                ReportRecord(
                    message_id=int(item["message_id"]),
                    channel_id=int(item["channel_id"]),
                    guild_id=int(item["guild_id"]),
                    author_id=int(item["author_id"]),
                    mod_role_id=int(item["mod_role_id"]) if item.get("mod_role_id") else None,
                    allow_hash_add=bool(item.get("allow_hash_add", True)),
                    kick_disabled=bool(item.get("kick_disabled", False)),
                    all_hashes=list(item.get("all_hashes", [])),
                    created_at=float(item.get("created_at", time.time())),
                )
            )
        return records

    def save_report(self, record: ReportRecord) -> None:
        reports = self.load_reports()
        reports = [r for r in reports if r.message_id != record.message_id]
        reports.append(record)
        self._write(reports)

    def delete_report(self, message_id: int) -> None:
        reports = [r for r in self.load_reports() if r.message_id != message_id]
        self._write(reports)

    def prune(self, max_age_s: float) -> None:
        now = time.time()
        reports = [r for r in self.load_reports() if now - r.created_at <= max_age_s]
        self._write(reports)

    def _write(self, records: Iterable[ReportRecord]) -> None:
        payload = {
            "reports": [
                {
                    "message_id": record.message_id,
                    "channel_id": record.channel_id,
                    "guild_id": record.guild_id,
                    "author_id": record.author_id,
                    "mod_role_id": record.mod_role_id,
                    "allow_hash_add": record.allow_hash_add,
                    "kick_disabled": record.kick_disabled,
                    "all_hashes": record.all_hashes,
                    "created_at": record.created_at,
                }
                for record in records
            ]
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

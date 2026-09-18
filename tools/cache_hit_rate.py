"""Report the hash-denylist "cache hit rate" from this bot's own report cards.

A "hit" is a report whose Reasons field says the images matched the known-bad
perceptual-hash denylist -- free, instant, no OpenAI call. A "miss" is
anything that had to be escalated to vision classification, which is where
the cost and the false-negative risk both live. The bot already writes this
distinction into every report embed's Reasons field, so this reads structured
data rather than classifying free text.

Usage: python tools/cache_hit_rate.py [max_pages]
Needs DISCORD_TOKEN in the environment (`set -a && . ./.env && set +a`).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HEADERS = {
    "Authorization": f"Bot {os.environ['DISCORD_TOKEN']}",
    "User-Agent": "DiscordBot (local, 1.0)",
}


def default_channel() -> str:
    """First guild's mod_channel in data/multi_server_config.json."""
    config_path = Path(__file__).resolve().parent.parent / "data" / "multi_server_config.json"
    config = json.loads(config_path.read_text())
    return next(iter(config.values()))["mod_channel"]


def fetch_page(channel: str, before: str | None) -> list[dict]:
    url = f"https://discord.com/api/v10/channels/{channel}/messages?limit=100"
    if before:
        url += f"&before={before}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def reasons_field(embed: dict) -> str:
    for f in embed.get("fields", []):
        if f.get("name") == "Reasons":
            return f.get("value", "")
    return ""


def classify(reason_text: str) -> str:
    # Only two paths ever call _send_report: a known-hash match, or a vision
    # classification (whose Reasons field is the model's own free-text
    # indicator list, e.g. "Offers a large bonus..., Uses urgency..."). So
    # anything that isn't a hash-match line is a miss, not a third category.
    return "hit" if "known bad hash match" in reason_text.lower() else "miss"


def main() -> None:
    channel = default_channel()
    max_pages = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    before = None
    rows: list[tuple[str, str]] = []
    for _ in range(max_pages):
        batch = fetch_page(channel, before)
        if not batch:
            break
        for msg in batch:
            for embed in msg.get("embeds", []):
                if embed.get("title") != "Possible crypto scam":
                    continue
                rows.append((msg["timestamp"], classify(reasons_field(embed))))
        before = batch[-1]["id"]
        if len(batch) < 100:
            break

    if not rows:
        print("No report messages found.")
        return

    rows.sort()
    total = len(rows)
    hits = sum(1 for _, cls in rows if cls == "hit")
    print(f"Window: {rows[0][0]} .. {rows[-1][0]}  ({total} reports)")
    print(f"Hits (known-hash match) : {hits} ({hits / total:.1%})")
    print(f"Misses (needed vision)  : {total - hits} ({(total - hits) / total:.1%})")

    now = datetime.now(timezone.utc)
    for days in (7, 14, 30):
        recent = [r for r in rows if (now - datetime.fromisoformat(r[0])).days < days]
        if recent:
            h = sum(1 for _, cls in recent if cls == "hit")
            print(f"Last {days:>2}d: {len(recent):4d} reports, {h:4d} hits ({h / len(recent):.1%})")

    by_week: dict[str, Counter] = defaultdict(Counter)
    for ts, cls in rows:
        wk = datetime.fromisoformat(ts).strftime("%Y-W%W")
        by_week[wk][cls] += 1
    print("\nBy week:")
    for wk in sorted(by_week):
        c = by_week[wk]
        t = sum(c.values())
        print(f"  {wk}: {t:4d} reports, {c['hit']:4d} hits ({c['hit'] / t:.0%})")


if __name__ == "__main__":
    main()

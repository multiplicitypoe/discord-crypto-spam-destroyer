# Discord crypto spam destroyer

This bot helps moderators deal with the “3-4 pictures of twitter or a crypto exchange” crypto scam spam. It checks known bad image hashes first, then (optionally) asks OpenAI to classify new patterns. It’s meant to be fast, cheap, and safe. 

## Why this exists

These scams are repetitive. Hashes catch the repeats quickly and for free. The model step is there for new variants, but you can turn it off if you want a hash‑only setup.

## What it does

- Watches guild text channels (ignores DMs).
- Only looks at messages with N or more images (default 3) to reduce noise and cost.
- Checks a file‑based hash denylist first.
- Optional OpenAI vision classification for unknown images.
  - Cost note: with `gpt-4o-mini`, our 512x512-ish scam images are a tiny fraction of a cent each. Check the OpenAI pricing page for current rates.
- Deletes scams and optionally kicks/bans or just reports.
- Mod report includes action taken, author roles, and locks buttons after one action.
- `/add_hash` slash command lets mods upload an image to add its hash.

## Screenshots

Known-bad hash match (auto delete + report):

![Bot report for a known hash match](data/screenshots/example_twitter_known_hashes.png "Known hash report with actions")

OpenAI vision detection (model‑flagged scam):

![Bot report for OpenAI detection](data/screenshots/example_crypto_openai_detected.png "OpenAI vision scam report")

## Quick start (Linux, macOS, WSL)

1) Clone the repo:

```bash
git clone <your-repo-url>
cd discord-crypto-spam-destroyer
```

2) Create `.env`:

```bash
DISCORD_TOKEN=...
OPENAI_API_KEY=...
```

3) Run:

```bash
make run-bot
```

## Where to get keys

Discord bot token:
- https://discord.com/developers/applications
- Create an application → Bot → Reset Token
- Enable **Message Content Intent** in the Bot settings

OpenAI API key (optional if using hash‑only mode):
- https://platform.openai.com/api-keys
- Create a key and paste it into `.env`
- If you’re using restricted keys, enable `chat.completions` request access and make sure the key can call `gpt-4o-mini`

If you want hash‑only mode, omit `OPENAI_API_KEY` and set `HASH_ONLY_MODE=true`.

## Install and invite the bot

1) In the Discord Developer Portal, enable **Message Content Intent**.
2) Invite the bot with these permissions:
   - Read Messages
   - Manage Messages
   - Kick Members / Ban Members (only if you want auto‑actions)

## Environment variables

Required:

- `DISCORD_TOKEN` — bot token from Discord.

Optional (defaults shown):

- `OPENAI_API_KEY` — OpenAI key for vision classification.
- `OPENAI_MODEL` (gpt-4o-mini) — model for image classification (our sample images are ~512x512, so per‑image cost is very low).
- `HASH_ONLY_MODE` (false) — skip OpenAI and use hash denylist only.
- `MIN_IMAGE_COUNT` (3) — min images before analysis.
- `MAX_IMAGES_TO_ANALYZE` (4) — cap on images per message.
- `KNOWN_BAD_HASH_PATH` (data/bad_hashes.txt) — denylist storage path.
- `ACTION_HIGH` (kick) — `kick`, `ban`, or `report_only` for high confidence.
- `ACTION_MEDIUM` (delete_and_report) — `delete_and_report` or `delete_only`.
- `CONFIDENCE_HIGH` (0.85) — high confidence cutoff.
- `CONFIDENCE_MEDIUM` (0.65) — medium confidence cutoff.
- `MOD_CHANNEL` (channel id or name, default 448522240749993990) — where reports go.
- `MOD_ROLE_ID` (restrict mod actions to role, default 410676614674907136).
- `REPORT_HIGH` (true) — also report high‑confidence cases to mods.
- `DOWNLOAD_TIMEOUT_S` (8.0) — image download timeout.
- `MAX_IMAGE_BYTES` (5000000) — max image size.

## Slash command

`/add_hash` — Upload an image to add its perceptual hash to the denylist. Use this when you spot a scam image before the model does.

## Running with Docker

```bash
# create .env with DISCORD_TOKEN and OPENAI_API_KEY

docker build -t discord-crypto-spam-destroyer .
docker run --env-file .env discord-crypto-spam-destroyer
```

## Running with a venv

```bash
make venv-install
make run-bot
```

## Tools

Generate hashes from known bad images:

```bash
make hashes
```

Test OpenAI vision on a sample image:

```bash
make check-images
```

## Testing

```bash
. .venv/bin/activate
pytest
```
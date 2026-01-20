# Discord Crypto Spam Destroyer

This bot helps mods deal with the “3-4 pictures of twitter or a crypto exchange” crypto scam spam. It checks known bad image hashes first, then (optionally) asks OpenAI to classify new patterns. It’s very fast when dealing with known images, and should just cost cents per day if you use the OpenAI API, for a large server. 

## Why this exists

These scams are repetitive, but hard to catch with the native Discord Automoderator, now that they stopped sending links to images, but rather direct uploads. Hashes catch the repeats quickly and for free. The model step is there for new variants, but you can turn it off if you want a hash‑only setup and don't mind some handholding. 

## What it does

- Watches guild text channels
- Only looks at messages with N or more images (default 3) to reduce noise and cost.
- Checks a file‑based hash denylist first.
- Optional OpenAI vision classification for unknown images.
  - Cost note: with `gpt-4o-mini`, our 512x512-ish scam images are a tiny fraction of a cent each. 
- Deletes scams and optionally kicks/bans or just reports to a configured mod channel. (See below for images)
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

(See `Where to get keys` below if you aren't sure where to find these)
```bash
DISCORD_TOKEN=...
OPENAI_API_KEY=...
MOD_CHANNEL=...
MOD_ROLE_ID=...
```

2.5) Optional: make sure your APIs are working before you run the full bot:

```bash
make test-discord # Sends a preview of the report UI to your mod channel
make test-openai # Asks OpenAI if the images stored under known_bad_scam_images are scams and reports back to you
```

3) Run:

```bash
make run-bot
```
(You can run with Docker, see below)

## Where to get keys

Discord bot token:
- https://discord.com/developers/applications
- Create an application → Bot → Reset Token
- Enable **Message Content Intent** in the Bot settings

OpenAI API key (optional if using hash‑only mode):
- https://platform.openai.com/api-keys
- Create a key and paste it into `.env`
- If you’re using restricted keys, enable `chat.completions` request access and make sure the key can call `gpt-4o-mini`

Don't forget to add your mod channel ID and Mod allow-list role by right clicking the channel and selecting copy ID on the role and the channel

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
- `MOD_CHANNEL` — channel id or name for reports.
- `MOD_ROLE_ID` — restrict mod actions to a role.

Optional (defaults shown):

- `OPENAI_API_KEY` — **Highly recommended**: OpenAI key for vision classification.
- `OPENAI_MODEL` (gpt-4o-mini) — model for image classification (our sample images are ~512x512, so per‑image cost is very low).
- `HASH_ONLY_MODE` (false) — skip OpenAI and use hash denylist only.
- `MIN_IMAGE_COUNT` (3) — min images on a message to trigger the bot. I find that these bots always post >=3 images, tune this lower at the risk of incurring more OpenAI API costs
- `MAX_IMAGES_TO_ANALYZE` (4) — cap on images per message.
- `KNOWN_BAD_HASH_PATH` (data/bad_hashes.txt) — denylist storage path.
- `ACTION_HIGH` (kick) — `kick`, `ban`, or `report_only` for high confidence.
- `ACTION_MEDIUM` (delete_and_report) — `delete_and_report` or `delete_only`.
- `CONFIDENCE_HIGH` (0.85) — high confidence cutoff.
- `CONFIDENCE_MEDIUM` (0.65) — medium confidence cutoff.
- `REPORT_HIGH` (true) — also report high‑confidence cases to mods.
- `DOWNLOAD_TIMEOUT_S` (8.0) — image download timeout.
- `MAX_IMAGE_BYTES` (5000000) — max image size.

## Slash command

`/add_hash` — Upload an image to add its perceptual hash to the denylist. Use this when you spot a scam image before the model does.

## Running with Docker

```bash
#  Make sure you created the .env file

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
make test-openai
```

Send a dummy mod report to verify Discord permissions:

```bash
make test-discord
```

## Testing

```bash
. .venv/bin/activate
pytest
```
# Discord Crypto Scam Bot Destroyer

This bot helps mods deal with the “3-4 pictures of twitter or a crypto exchange” crypto scam spam. It checks known bad image hashes first, then (optionally) asks OpenAI to classify new patterns. It’s very fast when dealing with known images, and should just cost cents per day if you use the OpenAI API, for a very large server. 

## What is this for?

These scams are repetitive, but hard to catch with the native Discord Automoderator, now that they stopped sending links to images, but rather direct uploads. Hashes catch the repeats quickly. The OpenAI vision step catches any new variants and makes this very hands-off, but you can turn it off if you want a hash‑only setup and don't mind some handholding. 

## What it does

- Watches channels in your server
- Checks every message with at least one image against the hash denylist. 
- Deletes scams and optionally kicks, bans, softbans (ban+unban) based on your config, or just reports to a configured mod channel
- Optional OpenAI vision classification for unknown images.
- Only calls OpenAI if the message has N or more images (default 3) to keep costs down.
  - You can switch to `gpt-4.1-mini` and `detail=low` to try adjusting costs for your uses.  Sequential classification stops early on high-confidence hits by default to keep costs down; enable parallel classification if you prefer speed over cost.
- `/add_hash` slash command lets mods upload an image to add its hash to the auto-delete/kick list.

## Screenshots

OpenAI vision detection (model-flagged scam):

![Bot report for OpenAI detection](data/screenshots/example_crypto_openai_detected.png "OpenAI vision scam report")

Known-bad hash match (auto delete + report):

![Bot report for a known hash match](data/screenshots/example_twitter_known_hashes.png "Known hash report with actions")

## Quick start (Linux, macOS, WSL)

1) Clone the repo:

```bash
git clone https://github.com/multiplicitypoe/discord-crypto-spam-destroyer.git
cd discord-crypto-spam-destroyer
```

2) Create `.env`:

(See `Where to get keys` below if you are not sure where to find these.)

```bash
DISCORD_TOKEN=...
OPENAI_API_KEY=...
MOD_CHANNEL=...
MOD_ROLE_ID=...
```
If you are configuring for multiple servers, see the appendix, then come back to step 2.5

2.5) Optional: make sure your APIs are working before you run the full bot:

```bash
make test-discord # Sends a preview of the report UI to your mod channel
make test-openai # Asks OpenAI if the images stored under known_bad_scam_images are scams and reports back to you
```

3) Run:

```bash
make run-bot
```

For Docker setup, see the Docker section below. 

Having trouble? Consider setting DEBUG_LOGS=true to print verbose logs for each message being processed

## Where to get keys

Discord bot token:
- https://discord.com/developers/applications
- Create an application -> Bot -> Reset Token
- Enable **Message Content Intent** in the Bot settings

OpenAI API key (optional if using hash-only mode):
- https://platform.openai.com/api-keys
- Create a key and paste it into `.env`
- If you are using restricted keys, enable `chat.completions` request access and make sure the key can call `gpt-4.1-mini`

Do not forget to copy your mod channel ID and mod role ID (right-click the channel or role -> Copy ID).

If you want hash-only mode (no AI image detection, just a fixed set of known bad images you can edit), omit `OPENAI_API_KEY` and set `HASH_ONLY_MODE=true`.

## Install and invite the bot

1) In the Discord Developer Portal, enable **Message Content Intent**.
2) Invite the bot with these permissions:
   - Read Messages, Send Messages
   - Attach Files / Allow Embeds
   - Manage Messages
   - Kick Members / Ban Members (only if you want auto-actions)
3) Ensure it has those read/attach/send permissions inside the Mod channel you specified in .env

## Environment variables

Required:

- `DISCORD_TOKEN` - bot token from Discord.
- `MOD_CHANNEL` - channel id or name for reports (omit if using multi-server config).
- `MOD_ROLE_ID` - restrict mod actions to a role (omit if using multi-server config).

Optional (defaults shown):

- `OPENAI_API_KEY` - **Highly recommended**. OpenAI key for vision classification.
- `OPENAI_MODEL` (gpt-4.1-mini) - model for image classification. On low-detail 512px images, `gpt-4.1-mini` is substantially cheaper in practice than `gpt-4o-mini`.
- `OPENAI_IMAGE_DETAIL` (low) - OpenAI vision detail level. `low` is faster/cheaper; `high` can be slower but more accurate on tiny text.
- `OPENAI_MAX_IMAGE_DIM` (512) - resizes images before sending to OpenAI; lower sizes are faster/cheaper, `0` disables resizing.
- `HASH_ONLY_MODE` (false) - skip OpenAI and use hash denylist only.
- `MIN_IMAGE_COUNT` (3) - min images required before OpenAI is called. Hash checks still run on any message with images.
- `MAX_IMAGES_TO_ANALYZE` (4) - cap on images analyzed per message.
- `PARALLEL_IMAGE_CLASSIFICATION` (false) - when true, classifies all selected images at once for speed; Costs **3x as much** if true. When false, runs sequentially with early-exit on high-confidence scams to reduce costs and still works fine for the common bot waves
- `KNOWN_BAD_HASH_PATH` (data/bad_hashes.txt) - denylist storage path.
- `ACTION_HIGH` (softban) - `kick`, `ban`, `softban` (ban+unban, deletes recent messages), or `report_only` for high confidence.
- `ACTION_MEDIUM` (delete_and_report) - `delete_and_report` or `delete_only`.
- `CONFIDENCE_HIGH` (0.85) - high confidence cutoff.
- `CONFIDENCE_MEDIUM` (0.65) - medium confidence cutoff.
- `REPORT_HIGH` (true) - also report high-confidence cases to mods.
- `REPORT_COOLDOWN_S` (20) - suppress duplicate reports per user during bursts.
- `REPORT_STORE_TTL_HOURS` (24) - keep report buttons alive across restarts for this many hours.
- `MESSAGE_PROCESSING_DELAY_S` (0.0) - delay all hash/AI processing for image messages; if another bot deletes the message during the delay, this bot skips it.
- `DEBUG_LOGS` (false) - verbose per-message logging for troubleshooting.
- `DOWNLOAD_TIMEOUT_S` (8.0) - image download timeout.
- `MAX_IMAGE_BYTES` (5000000) - max image size.
- `MULTI_SERVER_CONFIG_PATH` - path to a multi-server JSON config file (advanced; see appendix below). For Docker, use a path under `data/`.
- `TZ` (America/Los_Angeles) - optional container timezone override so that your logs are readable

## Slash command

`/add_hash` - Upload an image to add its perceptual hash to the denylist. Use this when you spot a scam image before the model does. 
* Hashes are saved via this Slash command and the Report embed button to the bad_hashes.txt file in your clone of this repository, assuming you start the bot with either the docker or non-docker Makefile targets. 
* If you want to dump images you know are scams and add their hashes all at once (it will preserve ones added through Discord), drop the images in the data/known_bad_scam_images folder and run `make hashes`


## Running with Docker

```bash
# Make sure you created the .env file
# `make run-docker-bot` does the below commands in one step (with sudo)
# Most of the arguments to docker run are for security hardening
docker build -t discord-crypto-spam-destroyer .
docker run --env-file .env -v "$(pwd)/data:/app/data" --read-only --tmpfs /tmp:rw,noexec,nosuid,nodev --cap-drop ALL --security-opt no-new-privileges --pids-limit 256 --memory 512m --cpus 1.0 --user "$(id -u):$(id -g)" discord-crypto-spam-destroyer
```

## Running with Poetry

```bash
make install
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
make test
```

## Appendix: Multi-server configuration (advanced)

If you run one bot instance across multiple servers, you can provide per-server overrides in a JSON file and point to it with `MULTI_SERVER_CONFIG_PATH`. This is optional; single-server setup with `.env` is still the recommended path.

Security note: the bot only processes a subset of embedded image types (png/jpeg/webp/gif/bmp) and enforces a maximum pixel limit to avoid decompression bombs.

`cp multi_server_config.json.example data/multi_server_config.json`, and then in your `.env`, which you still need, edit it to point at it (Docker users should keep it under `data/`):

```bash
MULTI_SERVER_CONFIG_PATH=data/multi_server_config.json
DISCORD_TOKEN=xxx
```

Each top-level key is a server id string. Values override any env defaults for that server. The only settings that cannot be overridden are the Discord bot token, hash file path, and report store TTL.

If any server is missing `mod_channel` or `mod_role_id` after merging defaults + overrides, the bot will refuse to start and log the missing server IDs.

Example JSON:

```json
{
  "123456789012345678": {
    "mod_channel": "mod-alerts",
    "mod_role_id": 111111111111111111,
    "action_high": "softban",
    "action_medium": "delete_and_report",
    "confidence_high": 0.85,
    "confidence_medium": 0.65,
    "report_high": true,
    "report_cooldown_s": 20.0,
    "hash_only_mode": false,
    "openai_model": "gpt-4.1-mini",
    "message_processing_delay_s": 1.5,
    "min_image_count": 3,
    "max_images_to_analyze": 4,
    "download_timeout_s": 8.0,
    "max_image_bytes": 5000000,
    "softban_delete_days": 1,
    "debug_logs": false
  },
  "987654321098765432": {
    "mod_channel": "security-log",
    "mod_role_id": 222222222222222222,
    "action_high": "report_only",
    "action_medium": "delete_only",
    "hash_only_mode": true,
    "message_processing_delay_s": 2.0
  }
}
```
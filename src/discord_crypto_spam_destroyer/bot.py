from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

import discord
from discord import app_commands

from discord_crypto_spam_destroyer.config import Settings, load_settings
from discord_crypto_spam_destroyer.models import VisionResult
from discord_crypto_spam_destroyer.utils.image import DownloadedImage
from discord_crypto_spam_destroyer.discord_ui.mod_report import (
    ReportContext,
    ReportView,
    build_indicator_text,
    build_mod_files,
    build_report_content,
)
from discord_crypto_spam_destroyer.hashes.phash import compute_phashes
from discord_crypto_spam_destroyer.hashes.store import FileHashStore, match_hashes
from discord_crypto_spam_destroyer.moderation.actions import apply_high_action, safe_delete
from discord_crypto_spam_destroyer.moderation.decision import decision_from_result
from discord_crypto_spam_destroyer.moderation.gating import select_images
from discord_crypto_spam_destroyer.utils.image import is_image_attachment, read_attachment, to_data_url
from discord_crypto_spam_destroyer.vision.openai_client import classify_images

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord_crypto_spam_destroyer")


class CryptoSpamBot(discord.Client):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        super().__init__(intents=intents)
        self.settings = settings
        self.hash_store = FileHashStore(Path(settings.known_bad_hash_path))
        self.tree = app_commands.CommandTree(self)
        self._report_cooldown: dict[int, float] = {}

    async def on_ready(self) -> None:
        logger.info("Logged in as %s", self.user)
        await self._register_commands()

    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return

        attachments = [a for a in message.attachments if is_image_attachment(a)]
        if self.settings.debug_logs:
            logger.info(
                "Message %s in #%s: %s attachments (%s images)",
                message.id,
                getattr(message.channel, "name", "unknown"),
                len(message.attachments),
                len(attachments),
            )
        downloaded: list[DownloadedImage] = []
        for attachment in attachments[: self.settings.max_images_to_analyze]:
            downloaded_image = await read_attachment(
                attachment,
                self.settings.max_image_bytes,
                self.settings.download_timeout_s,
            )
            if downloaded_image:
                downloaded.append(downloaded_image)

        if not downloaded:
            if self.settings.debug_logs:
                logger.info("Message %s skipped: could not download images", message.id)
            return

        images = [image.data for image in downloaded]
        phashes = compute_phashes(images)
        known_bad = self.hash_store.load()
        match = match_hashes(phashes, known_bad)
        if match.matched:
            logger.info("Message %s matched known bad hashes", message.id)
            delete_result = await safe_delete(message)
            action_result = await self._apply_high_action_with_mod_check(
                message.guild,
                message.author,
                confidence=1.0,
                reason="Known bad crypto scam hash",
            )
            if self._report_allowed(message.author.id):
                await self._send_report(
                    message,
                    message.author,
                    vision_result=None,
                    downloaded=downloaded,
                    all_hashes=phashes,
                    reason_override="Known bad hash match",
                    action_taken=self._format_action_taken(delete_result, action_result),
                    allow_hash_add=False,
                )
            return

        if not phashes:
            if self.settings.debug_logs:
                logger.info("Message %s skipped: no valid hashes", message.id)
            return

        selection = select_images(
            [a.url for a in attachments],
            self.settings.min_image_count,
            self.settings.max_images_to_analyze,
        )
        if not selection.qualifies:
            if self.settings.debug_logs:
                logger.info(
                    "Message %s skipped: need %s images, got %s",
                    message.id,
                    self.settings.min_image_count,
                    selection.total_images,
                )
            return

        if self.settings.hash_only_mode:
            if self.settings.debug_logs:
                logger.info("Message %s skipped: hash-only mode", message.id)
            return

        if not self.settings.openai_api_key:
            if self.settings.debug_logs:
                logger.info("Message %s skipped: OPENAI_API_KEY not set", message.id)
            return

        images_base64 = [to_data_url(image) for image in downloaded]
        try:
            vision_result = await asyncio.to_thread(
                classify_images,
                self.settings.openai_api_key,
                self.settings.openai_model,
                images_base64,
            )
        except Exception:
            logger.exception("OpenAI vision classification failed")
            return

        logger.info(
            "Message %s vision result: scam=%s confidence=%.2f",
            message.id,
            vision_result.is_crypto_scam,
            vision_result.confidence,
        )

        decision = decision_from_result(
            vision_result,
            self.settings.confidence_high,
            self.settings.confidence_medium,
        )
        if not decision.is_scam:
            if self.settings.debug_logs:
                logger.info("Message %s not flagged: %s", message.id, decision.reason)
            return

        delete_result = await safe_delete(message)
        if decision.confidence_band.value == "high":
            logger.info("Message %s high confidence scam", message.id)
            action_result = await self._apply_high_action_with_mod_check(
                message.guild,
                message.author,
                confidence=vision_result.confidence,
                reason="High confidence crypto scam",
            )
            if self.settings.report_high and self._report_allowed(message.author.id):
                logger.info("Message %s reporting high confidence scam", message.id)
                await self._send_report(
                    message,
                    message.author,
                    vision_result,
                    downloaded,
                    phashes,
                    action_taken=self._format_action_taken(delete_result, action_result),
                    allow_hash_add=True,
                )
            return

        if self.settings.action_medium == "delete_only":
            if self.settings.debug_logs:
                logger.info("Message %s deleted without report", message.id)
            return

        if self._report_allowed(message.author.id):
            logger.info("Message %s medium confidence scam, sending report", message.id)
            await self._send_report(
                message,
                message.author,
                vision_result,
                downloaded,
                phashes,
                action_taken=self._format_action_taken(delete_result, None),
                allow_hash_add=True,
            )

    async def _send_report(
        self,
        message: discord.Message,
        author: discord.abc.User,
        vision_result: VisionResult | None,
        downloaded: list[DownloadedImage],
        all_hashes: list[str],
        reason_override: str | None = None,
        action_taken: str = "none",
        allow_hash_add: bool = True,
    ) -> None:
        if message.guild is None:
            return
        channel = await self._resolve_mod_channel(message.guild)
        if channel is None:
            return
        if vision_result:
            indicators = build_indicator_text(
                vision_result.indicators.domains,
                vision_result.indicators.amounts,
                vision_result.indicators.wallet_addresses,
            )
            confidence = vision_result.confidence
            reasons = vision_result.reasons
        else:
            indicators = "none"
            confidence = 1.0
            reasons = [reason_override or "Known bad hash"]
        action_suggestion = (
            f"/kick {author.id}" if self.settings.action_high == "kick" else f"/ban {author.id}"
        )
        author_roles = await self._format_author_roles(message.guild, author)
        content = build_report_content(
            message,
            author,
            confidence,
            reasons,
            indicators,
            action_suggestion,
            action_taken,
            author_roles,
        )
        context = ReportContext(
            guild=message.guild,
            channel=channel,
            message=message,
            author=author,
            images=downloaded,
            action_high=self.settings.action_high,
            hash_store=self.hash_store,
            all_hashes=list(all_hashes),
            mod_role_id=self.settings.mod_role_id,
            allow_hash_add=allow_hash_add,
            kick_disabled=self.settings.action_high != "kick",
        )
        view = ReportView(context)
        files = build_mod_files(downloaded)
        await channel.send(content=content, files=files, view=view)

    async def _register_commands(self) -> None:
        if not self.settings.mod_channel:
            return
        command = app_commands.Command(
            name="add_hash",
            description="Add an image hash to the denylist.",
            callback=self._add_hash_command,
        )
        self.tree.add_command(command)
        await self.tree.sync()

    async def _add_hash_command(
        self,
        interaction: discord.Interaction,
        image: discord.Attachment,
    ) -> None:
        if self.settings.mod_role_id:
            if not interaction.user or not isinstance(interaction.user, discord.Member):
                await interaction.response.send_message("Permission check failed.", ephemeral=True)
                return
            if not any(role.id == self.settings.mod_role_id for role in interaction.user.roles):
                await interaction.response.send_message("Missing Mod role.", ephemeral=True)
                return
        downloaded = await read_attachment(image, self.settings.max_image_bytes, self.settings.download_timeout_s)
        if not downloaded:
            await interaction.response.send_message("Failed to read image.", ephemeral=True)
            return
        phashes = compute_phashes([downloaded.data])
        if not phashes:
            await interaction.response.send_message("No hash generated from image.", ephemeral=True)
            return
        added = 0
        for phash in phashes:
            self.hash_store.add(phash)
            added += 1
        await interaction.response.send_message(f"Added {added} hash(es) to denylist.", ephemeral=True)

    async def _resolve_mod_channel(self, guild: discord.Guild) -> discord.TextChannel | None:
        if not self.settings.mod_channel:
            return None
        if self.settings.mod_channel.isdigit():
            channel = guild.get_channel(int(self.settings.mod_channel))
            if isinstance(channel, discord.TextChannel):
                return channel
            return None
        for channel in guild.text_channels:
            if channel.name == self.settings.mod_channel:
                return channel
        return None

    async def _apply_high_action_with_mod_check(
        self,
        guild: discord.Guild,
        author: discord.abc.User,
        confidence: float,
        reason: str,
    ) -> str:
        if confidence < 0.95:
            return "no action (below 0.95)"
        if self.settings.action_high == "report_only":
            return "report only"
        if self.settings.mod_role_id:
            member = await self._get_member(guild, author.id)
            if member and any(role.id == self.settings.mod_role_id for role in member.roles):
                return "no kick (author is Mod)"
        success = await apply_high_action(guild, author.id, self.settings.action_high, reason)
        if not success:
            return "kick failed"
        if self.settings.action_high == "softban":
            return "softban"
        if self.settings.action_high == "ban":
            return "ban"
        return "kick"

    def _format_action_taken(self, deleted: bool, action_result: str | None) -> str:
        actions = ["deleted" if deleted else "not deleted"]
        if action_result:
            actions.append(action_result)
        return ", ".join(actions)

    def _report_allowed(self, user_id: int) -> bool:
        cooldown = self.settings.report_cooldown_s
        if cooldown <= 0:
            return True
        now = time.monotonic()
        last = self._report_cooldown.get(user_id)
        if last and now - last < cooldown:
            return False
        self._report_cooldown[user_id] = now
        return True

    async def _get_member(self, guild: discord.Guild, user_id: int) -> discord.Member | None:
        member = guild.get_member(user_id)
        if member:
            return member
        try:
            return await guild.fetch_member(user_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

    async def _format_author_roles(self, guild: discord.Guild, author: discord.abc.User) -> str:
        member = await self._get_member(guild, author.id)
        if not member:
            return "(roles unknown)"
        roles = [role.name for role in member.roles if role.name != "@everyone"]
        if not roles:
            return "(no roles)"
        return f"({', '.join(roles)})"


def main() -> None:
    settings = load_settings()
    bot = CryptoSpamBot(settings)
    bot.run(settings.discord_token)


if __name__ == "__main__":
    main()

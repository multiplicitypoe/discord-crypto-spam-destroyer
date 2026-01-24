from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

import discord
from discord import app_commands

from discord_crypto_spam_destroyer.config import ResolvedSettings, Settings, load_settings, resolve_settings
from discord_crypto_spam_destroyer.models import VisionResult
from discord_crypto_spam_destroyer.utils.image import DownloadedImage
from discord_crypto_spam_destroyer.discord_ui.mod_report import (
    ReportContext,
    ReportView,
    build_indicator_text,
    build_mod_files,
    build_report_embed,
)
from discord_crypto_spam_destroyer.discord_ui.report_store import ReportRecord, ReportStore
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
        self._report_cooldown: dict[tuple[int, int], float] = {}
        self._settings_cache: dict[int, ResolvedSettings] = {}
        self._missing_mod_channel_warned: set[int] = set()
        self.report_store = ReportStore(Path("data") / "report_store.json")

    async def on_ready(self) -> None:
        logger.info("Logged in as %s", self.user)
        await self._validate_guild_settings()
        await self._register_commands()
        await self._restore_persistent_views()

    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or message.author.bot:
            return

        attachments = [a for a in message.attachments if is_image_attachment(a)]
        if not attachments:
            return

        if message.guild is None:
            logger.info("Message %s missing guild before processing", message.id)
            return
        guild = message.guild
        settings = self._get_resolved_settings(guild.id)

        if settings.message_processing_delay_s > 0:
            await asyncio.sleep(settings.message_processing_delay_s)
            try:
                message = await message.channel.fetch_message(message.id)
            except discord.NotFound:
                logger.info("Message %s was deleted before processing", message.id)
                return
            except discord.Forbidden:
                logger.info("Message %s became inaccessible before processing", message.id)
                return
            except discord.HTTPException:
                logger.exception("Message %s could not be fetched before processing", message.id)
                return

            if message.guild is None:
                logger.info("Message %s missing guild after delay", message.id)
                return

            attachments = [a for a in message.attachments if is_image_attachment(a)]
            if not attachments:
                return

        if settings.debug_logs:
            logger.info(
                "Message %s in #%s: %s attachments (%s images)",
                message.id,
                getattr(message.channel, "name", "unknown"),
                len(message.attachments),
                len(attachments),
            )
        downloaded: list[DownloadedImage] = []
        for attachment in attachments[: settings.max_images_to_analyze]:
            downloaded_image = await read_attachment(
                attachment,
                settings.max_image_bytes,
                settings.download_timeout_s,
            )
            if downloaded_image:
                downloaded.append(downloaded_image)

        if not downloaded:
            if settings.debug_logs:
                logger.info("Message %s skipped: could not download images", message.id)
            return

        images = [image.data for image in downloaded]
        try:
            phashes = await asyncio.wait_for(
                asyncio.to_thread(compute_phashes, images),
                timeout=2.0,
            )
        except asyncio.TimeoutError:
            logger.info("Message %s skipped: hash computation timed out", message.id)
            return
        known_bad = self.hash_store.load()
        match = match_hashes(phashes, known_bad)
        if match.matched:
            logger.info("Message %s matched known bad hashes", message.id)
            delete_result = await safe_delete(message)
            author_roles = await self._format_author_roles(guild, message.author)
            action_result = await self._apply_high_action_with_mod_check(
                guild,
                message.author,
                confidence=1.0,
                reason="Known bad crypto scam hash",
                settings=settings,
            )

            if self._report_allowed(guild.id, message.author.id, settings):
                logger.info("Report sent (hash match) for message %s", message.id)
                await self._send_report(
                    message,
                    message.author,
                    vision_result=None,
                    downloaded=downloaded,
                    all_hashes=phashes,
                    reason_override="Known bad hash match",
                    action_taken=self._format_action_taken(delete_result, action_result),
                    allow_hash_add=False,
                    kick_disabled=self._should_disable_kick(action_result),
                    action_suggestion_override="No action necessary",
                    author_roles_override=author_roles,
                )
            return

        if not phashes:
            if settings.debug_logs:
                logger.info("Message %s skipped: no valid hashes", message.id)
            return

        selection = select_images(
            [a.url for a in attachments],
            settings.min_image_count,
            settings.max_images_to_analyze,
        )
        if not selection.qualifies:
            if settings.debug_logs:
                logger.info(
                    "Message %s skipped: need %s images, got %s",
                    message.id,
                    settings.min_image_count,
                    selection.total_images,
                )
            return

        if settings.hash_only_mode:
            if settings.debug_logs:
                logger.info("Message %s skipped: hash-only mode", message.id)
            return

        if not settings.openai_api_key:
            if settings.debug_logs:
                logger.info("Message %s skipped: OPENAI_API_KEY not set", message.id)
            return

        try:
            vision_result = await self._classify_images(message.id, settings, downloaded)
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
            settings.confidence_high,
            settings.confidence_medium,
        )
        if not decision.is_scam:
            if settings.debug_logs:
                logger.info("Message %s not flagged: %s", message.id, decision.reason)
            return

        delete_result = await safe_delete(message)
        author_roles = await self._format_author_roles(guild, message.author)
        if decision.confidence_band.value == "high":
            logger.info("Message %s high confidence scam", message.id)
            action_result = await self._apply_high_action_with_mod_check(
                guild,
                message.author,
                confidence=vision_result.confidence,
                reason="High confidence crypto scam",
                settings=settings,
            )
            if settings.report_high and self._report_allowed(guild.id, message.author.id, settings):
                logger.info("Report sent (high confidence) for message %s", message.id)
                await self._send_report(
                    message,
                    message.author,
                    vision_result,
                    downloaded,
                    phashes,
                    action_taken=self._format_action_taken(delete_result, action_result),
                    allow_hash_add=True,
                    kick_disabled=self._should_disable_kick(action_result),
                    action_suggestion_override="Add hashes",
                    author_roles_override=author_roles,
                )
            return

        if settings.action_medium == "delete_only":
            if settings.debug_logs:
                logger.info("Message %s deleted without report", message.id)
            return

        if self._report_allowed(guild.id, message.author.id, settings):
            logger.info("Report sent (medium confidence) for message %s", message.id)
            await self._send_report(
                message,
                message.author,
                vision_result,
                downloaded,
                phashes,
                action_taken=self._format_action_taken(delete_result, None),
                allow_hash_add=True,
                kick_disabled=False,
                action_suggestion_override="Review and decide",
                author_roles_override=author_roles,
            )


    async def _classify_images(
        self,
        message_id: int,
        settings: ResolvedSettings,
        downloaded: list[DownloadedImage],
    ) -> VisionResult:
        best_scam: VisionResult | None = None
        best_non_scam: VisionResult | None = None
        total = len(downloaded)
        api_key = settings.openai_api_key
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        if settings.parallel_image_classification:
            tasks = [
                asyncio.to_thread(
                    classify_images,
                    api_key,
                    settings.openai_model,
                    [to_data_url(image)],
                )
                for image in downloaded
            ]
            results = await asyncio.gather(*tasks)
            if settings.debug_logs:
                logger.info(
                    "Classified %s images in parallel for message %s",
                    total,
                    message_id,
                )
            for result in results:
                if result.is_crypto_scam:
                    if best_scam is None or result.confidence > best_scam.confidence:
                        best_scam = result
                else:
                    if best_non_scam is None or result.confidence > best_non_scam.confidence:
                        best_non_scam = result
        else:
            for index, image in enumerate(downloaded, start=1):
                if settings.debug_logs:
                    logger.info(
                        "Classifying image %s/%s for message %s",
                        index,
                        total,
                        message_id,
                    )
                result = await asyncio.to_thread(
                    classify_images,
                    api_key,
                    settings.openai_model,
                    [to_data_url(image)],
                )
                if result.is_crypto_scam:
                    if best_scam is None or result.confidence > best_scam.confidence:
                        best_scam = result
                    if result.confidence >= settings.confidence_high:
                        if settings.debug_logs:
                            logger.info(
                                "Message %s early exit: high confidence scam on image %s/%s",
                                message_id,
                                index,
                                total,
                            )
                        return result
                else:
                    if best_non_scam is None or result.confidence > best_non_scam.confidence:
                        best_non_scam = result
        if best_scam:
            return best_scam
        if best_non_scam:
            return best_non_scam
        raise RuntimeError("No images available for classification")

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
        kick_disabled: bool = False,
        action_suggestion_override: str | None = None,
        author_roles_override: str | None = None,
    ) -> None:
        if message.guild is None:
            return
        settings = self._get_resolved_settings(message.guild.id)
        channel = await self._resolve_mod_channel(message.guild, settings)
        if channel is None:
            await self._warn_missing_mod_channel(message.guild, settings)
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
        action_suggestion = action_suggestion_override or (
            f"/kick {author.id}" if settings.action_high == "kick" else f"/ban {author.id}"
        )
        author_roles = author_roles_override or await self._format_author_roles(message.guild, author)
        embed = build_report_embed(
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
            hash_store=self.hash_store,
            all_hashes=list(all_hashes),
            mod_role_id=settings.mod_role_id,
            allow_hash_add=allow_hash_add,
            kick_disabled=kick_disabled,
            report_store=self.report_store,
            report_record=None,
        )
        view = ReportView(context, timeout=None)
        files = build_mod_files(downloaded)
        sent_message = await channel.send(embed=embed, files=files, view=view)
        report_record = ReportRecord(
            message_id=sent_message.id,
            channel_id=channel.id,
            guild_id=message.guild.id,
            author_id=author.id,
            mod_role_id=settings.mod_role_id,
            allow_hash_add=allow_hash_add,
            kick_disabled=kick_disabled,
            all_hashes=list(all_hashes),
            created_at=time.time(),
        )
        self.report_store.save_report(report_record)
        context.report_record = report_record

    async def _register_commands(self) -> None:
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
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        settings = self._get_resolved_settings(interaction.guild.id)
        if settings.mod_role_id:
            if not interaction.user or not isinstance(interaction.user, discord.Member):
                await interaction.response.send_message("Permission check failed.", ephemeral=True)
                return
            if not any(role.id == settings.mod_role_id for role in interaction.user.roles):
                await interaction.response.send_message("Missing Mod role.", ephemeral=True)
                return
        mod_channel = await self._resolve_mod_channel(interaction.guild, settings)
        if not mod_channel:
            await self._warn_missing_mod_channel(interaction.guild, settings)
            await interaction.response.send_message("Mod channel not found.", ephemeral=True)
            return
        downloaded = await read_attachment(image, settings.max_image_bytes, settings.download_timeout_s)
        if not downloaded:
            await interaction.response.send_message("Failed to read image.", ephemeral=True)
            return
        phashes = compute_phashes([downloaded.data])
        if not phashes:
            await interaction.response.send_message("No hash generated from image.", ephemeral=True)
            return
        unique_hashes: list[str] = []
        seen: set[str] = set()
        for phash in phashes:
            if phash in seen:
                continue
            unique_hashes.append(phash)
            seen.add(phash)
        existing = self.hash_store.load()
        new_hashes = [phash for phash in unique_hashes if phash not in existing]
        already_known = [phash for phash in unique_hashes if phash in existing]
        for phash in new_hashes:
            self.hash_store.add(phash)
        added = len(new_hashes)
        already_count = len(already_known)
        added_label = "hash" if added == 1 else "hashes"
        if added == 0:
            result_detail = f"Hashes already known ({already_count})."
        elif already_count:
            result_detail = f"Added {added} {added_label} ({already_count} already known)."
        else:
            result_detail = f"Added {added} {added_label}."
        actor = interaction.user.mention if interaction.user else "Unknown"
        actor_id = interaction.user.id if interaction.user else "unknown"
        channel = interaction.channel
        if isinstance(channel, discord.abc.GuildChannel):
            source_channel = channel.mention
        else:
            source_channel = "Unknown channel"
        embed = discord.Embed(title="Manual hash add", color=discord.Color.red())
        embed.add_field(name="Added by", value=f"{actor} ({actor_id})", inline=False)
        embed.add_field(name="Source", value=source_channel, inline=False)
        embed.add_field(name="Image", value=f"{image.filename}\n{image.url}", inline=False)
        embed.add_field(name="Hashes", value=", ".join(unique_hashes), inline=False)
        embed.add_field(name="Result", value=result_detail, inline=False)
        embed.set_image(url=image.url)
        await mod_channel.send(embed=embed)
        await interaction.response.send_message(
            f"{result_detail} Logged to {mod_channel.mention}.",
        )

    async def _resolve_mod_channel(
        self,
        guild: discord.Guild,
        settings: ResolvedSettings,
    ) -> discord.TextChannel | None:
        if not settings.mod_channel:
            return None
        if settings.mod_channel.isdigit():
            channel = guild.get_channel(int(settings.mod_channel))
            if isinstance(channel, discord.TextChannel):
                return channel
            return None
        for channel in guild.text_channels:
            if channel.name == settings.mod_channel:
                return channel
        return None

    async def _warn_missing_mod_channel(
        self,
        guild: discord.Guild,
        settings: ResolvedSettings,
    ) -> None:
        if guild.id in self._missing_mod_channel_warned:
            return
        logger.info("Mod channel is not configured for guild %s", guild.id)
        self._missing_mod_channel_warned.add(guild.id)
        channel = await self._select_fallback_channel(guild)
        if not channel:
            return
        role_mention = f"<@&{settings.mod_role_id}> " if settings.mod_role_id else ""
        await channel.send(
            f"{role_mention}Mod channel is not configured for this server. "
            "Set MOD_CHANNEL or a per-guild mod_channel in the multi-server config."
        )

    async def _select_fallback_channel(
        self,
        guild: discord.Guild,
    ) -> discord.TextChannel | None:
        me = guild.me
        if me is None:
            return None
        if guild.system_channel and guild.system_channel.permissions_for(me).send_messages:
            return guild.system_channel
        for channel in guild.text_channels:
            if channel.permissions_for(me).send_messages:
                return channel
        return None

    async def _apply_high_action_with_mod_check(
        self,
        guild: discord.Guild,
        author: discord.abc.User,
        confidence: float,
        reason: str,
        settings: ResolvedSettings,
    ) -> str:
        if settings.action_high == "report_only":
            return "report only"
        if settings.mod_role_id:
            member = await self._get_member(guild, author.id)
            if member and any(role.id == settings.mod_role_id for role in member.roles):
                return "no kick (author is Mod)"
        success = await apply_high_action(
            guild,
            author.id,
            settings.action_high,
            reason,
            softban_delete_days=settings.softban_delete_days,
        )
        if not success:
            return "kick failed"
        if settings.action_high == "softban":
            return "softban"
        if settings.action_high == "ban":
            return "ban"
        return "kick"

    def _format_action_taken(self, deleted: bool, action_result: str | None) -> str:
        actions = ["deleted" if deleted else "not deleted"]
        if action_result:
            actions.append(action_result)
        return ", ".join(actions)

    def _should_disable_kick(self, action_result: str | None) -> bool:
        return action_result in {"kick", "ban", "softban"}

    def _report_allowed(self, guild_id: int, user_id: int, settings: ResolvedSettings) -> bool:
        cooldown = settings.report_cooldown_s
        if cooldown <= 0:
            return True
        now = time.monotonic()
        key = (guild_id, user_id)
        last = self._report_cooldown.get(key)
        if last and now - last < cooldown:
            return False
        self._report_cooldown[key] = now
        return True

    async def _get_member(self, guild: discord.Guild, user_id: int) -> discord.Member | None:
        member = guild.get_member(user_id)
        if member:
            return member
        try:
            return await guild.fetch_member(user_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

    async def _fetch_channel(self, channel_id: int) -> discord.TextChannel | None:
        channel = self.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        try:
            fetched = await self.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None
        return fetched if isinstance(fetched, discord.TextChannel) else None

    async def _restore_persistent_views(self) -> None:
        ttl_s = self.settings.report_store_ttl_hours * 3600
        self.report_store.prune(ttl_s)
        records = self.report_store.load_reports()
        restored = 0
        for record in records:
            channel = await self._fetch_channel(record.channel_id)
            if not channel:
                self.report_store.delete_report(record.message_id)
                continue
            try:
                report_message = await channel.fetch_message(record.message_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                self.report_store.delete_report(record.message_id)
                continue
            author: discord.abc.User | None = None
            try:
                author = await self.fetch_user(record.author_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                author = channel.guild.get_member(record.author_id)
            if author is None:
                self.report_store.delete_report(record.message_id)
                continue
            context = ReportContext(
                guild=channel.guild,
                channel=channel,
                message=report_message,
                author=author,
                images=[],
                hash_store=self.hash_store,
                all_hashes=list(record.all_hashes),
                mod_role_id=record.mod_role_id,
                allow_hash_add=record.allow_hash_add,
                kick_disabled=record.kick_disabled,
                report_store=self.report_store,
                report_record=record,
            )
            view = ReportView(context, timeout=None)
            self.add_view(view, message_id=record.message_id)
            restored += 1
        if restored:
            logger.info("Restored %s report views", restored)

    def _get_resolved_settings(self, guild_id: int) -> ResolvedSettings:
        cached = self._settings_cache.get(guild_id)
        if cached:
            return cached
        resolved = resolve_settings(self.settings, guild_id)
        self._settings_cache[guild_id] = resolved
        return resolved

    async def _validate_guild_settings(self) -> None:
        missing: list[str] = []
        for guild in self.guilds:
            resolved = self._get_resolved_settings(guild.id)
            missing_fields: list[str] = []
            if not resolved.mod_channel:
                missing_fields.append("MOD_CHANNEL")
            if not resolved.mod_role_id:
                missing_fields.append("MOD_ROLE_ID")
            if missing_fields:
                missing.append(f"{guild.id} ({', '.join(missing_fields)})")
        if missing:
            missing_ids = ", ".join(missing)
            logger.error("Missing required settings for guild(s): %s", missing_ids)
            await self.close()
            raise RuntimeError("Missing required settings for guild(s): " + missing_ids)

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

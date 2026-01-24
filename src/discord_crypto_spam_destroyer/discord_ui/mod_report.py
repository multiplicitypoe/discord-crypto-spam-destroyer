from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import logging
import discord

from discord_crypto_spam_destroyer.hashes.store import FileHashStore
from discord_crypto_spam_destroyer.moderation.actions import apply_high_action
from discord_crypto_spam_destroyer.utils.image import DownloadedImage, build_discord_files
from discord_crypto_spam_destroyer.discord_ui.report_store import ReportRecord, ReportStore

logger = logging.getLogger("discord_crypto_spam_destroyer")


@dataclass
class ReportContext:
    guild: discord.Guild
    channel: discord.TextChannel
    message: discord.Message
    author: discord.abc.User
    images: Iterable[DownloadedImage]
    hash_store: FileHashStore
    all_hashes: list[str]
    mod_role_id: int | None
    allow_hash_add: bool
    kick_disabled: bool
    report_store: ReportStore
    report_record: ReportRecord | None


class ReportView(discord.ui.View):
    def __init__(
        self,
        context: ReportContext,
        timeout: float | None = None,
    ) -> None:
        super().__init__(timeout=timeout)
        self.context = context
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.label == "Kick":
                child.disabled = context.kick_disabled
            if isinstance(child, discord.ui.Button) and child.label == "Add Hashes":
                child.disabled = not context.allow_hash_add
                if not context.allow_hash_add:
                    child.label = "Hashes already known"

    async def _ensure_permissions(self, interaction: discord.Interaction, permission: str) -> bool:
        if not interaction.user or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "Permissions check failed.", ephemeral=True
            )
            return False
        if self.context.mod_role_id:
            if not any(role.id == self.context.mod_role_id for role in interaction.user.roles):
                await interaction.response.send_message("Missing Mod role.", ephemeral=True)
                return False
        if permission == "kick" and not interaction.user.guild_permissions.kick_members:
            await interaction.response.send_message("Missing kick permission.", ephemeral=True)
            return False
        if permission == "ban" and not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("Missing ban permission.", ephemeral=True)
            return False
        return True

    async def _finalize_action(self, interaction: discord.Interaction, result: str) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        actor = interaction.user.mention if interaction.user else "Unknown"
        action_text = f"Action by {actor}: {result}"
        if self.context.report_record:
            self.context.report_store.delete_report(self.context.report_record.message_id)
        if interaction.message and interaction.message.embeds:
            embed = interaction.message.embeds[0]
            updated = False
            for index, field in enumerate(embed.fields):
                field_name = field.name or ""
                if field_name.lower() == "action taken":
                    prior = field.value or "none"
                    combined = f"{prior}, {action_text}" if prior and prior.lower() != "none" else action_text
                    embed.set_field_at(index, name=field_name, value=combined, inline=field.inline)
                    updated = True
                    break
            if not updated:
                embed.add_field(name="Action taken", value=action_text, inline=False)
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                await interaction.response.edit_message(embed=embed, view=self)
            return
        content = interaction.message.content if interaction.message else ""
        updated_content = (
            f"{content}\n\n{action_text}" if content else action_text
        )
        if interaction.response.is_done():
            await interaction.edit_original_response(content=updated_content, view=self)
        else:
            await interaction.response.edit_message(content=updated_content, view=self)

    @discord.ui.button(label="Kick", style=discord.ButtonStyle.danger, custom_id="report_kick")
    async def kick_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not await self._ensure_permissions(interaction, "kick"):
            return
        if self.context.kick_disabled:
            await self._finalize_action(interaction, "Kick disabled for auto-actions")
            return
        logger.info("Mod action: kick pressed by %s", interaction.user)
        success = await apply_high_action(
            self.context.guild,
            self.context.author.id,
            "kick",
            "Manual mod action from report",
        )
        result = "Kicked" if success else "Kick failed or user gone"
        await self._finalize_action(interaction, result)

    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger, custom_id="report_ban")
    async def ban_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not await self._ensure_permissions(interaction, "ban"):
            return
        logger.info("Mod action: ban pressed by %s", interaction.user)
        success = await apply_high_action(
            self.context.guild,
            self.context.author.id,
            "ban",
            "Manual mod action from report",
        )
        result = "Banned" if success else "Ban failed or user gone"
        await self._finalize_action(interaction, result)

    @discord.ui.button(
        label="No action necessary",
        style=discord.ButtonStyle.secondary,
        custom_id="report_ignore",
    )
    async def ignore_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        logger.info("Mod action: no action necessary pressed by %s", interaction.user)
        await self._finalize_action(interaction, "No action necessary")

    @discord.ui.button(label="Add Hashes", style=discord.ButtonStyle.primary, custom_id="report_add_hashes")
    async def add_hash_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not await self._ensure_permissions(interaction, "kick"):
            return
        existing = self.context.hash_store.load()
        new_hashes = [phash for phash in self.context.all_hashes if phash not in existing]
        already_known = len(self.context.all_hashes) - len(new_hashes)
        if not self.context.allow_hash_add:
            logger.info("Mod action: add hashes pressed by %s (disabled)", interaction.user)
            if not new_hashes:
                await self._finalize_action(interaction, "Hashes already known")
            else:
                await self._finalize_action(interaction, "Hash add disabled")
            return
        if not new_hashes:
            logger.info("Mod action: add hashes pressed by %s (no-op)", interaction.user)
            await self._finalize_action(interaction, "Hashes already known")
            return
        added = 0
        for phash in new_hashes:
            self.context.hash_store.add(phash)
            added += 1
        logger.info(
            "Mod action: add hashes pressed by %s (%s added, %s known)",
            interaction.user,
            added,
            already_known,
        )
        added_label = "hash" if added == 1 else "hashes"
        if already_known:
            known_label = "hash" if already_known == 1 else "hashes"
            result = f"Added {added} {added_label} ({already_known} already known {known_label})"
        else:
            result = f"Added {added} {added_label}"
        await self._finalize_action(interaction, result)


def build_report_embed(
    message: discord.Message,
    author: discord.abc.User,
    confidence: float,
    reasons: Iterable[str],
    indicators: str,
    action_suggestion: str,
    action_taken: str,
    author_roles: str,
) -> discord.Embed:
    reason_text = ", ".join(reasons) if reasons else "none"
    suggested = f"`{action_suggestion}`" if action_suggestion.startswith("/") else action_suggestion
    embed = discord.Embed(title="Possible crypto scam", color=discord.Color.red())
    embed.add_field(
        name="Author",
        value=f"{author.mention} ({author.id}) {author_roles}",
        inline=False,
    )
    embed.add_field(
        name="Message link",
        value=message.jump_url,
        inline=False,
    )
    embed.add_field(name="Confidence", value=f"{confidence:.2f}", inline=True)
    embed.add_field(name="Reasons", value=reason_text, inline=False)
    embed.add_field(name="Indicators", value=indicators, inline=False)
    embed.add_field(name="Suggested", value=suggested, inline=False)
    embed.add_field(name="Action taken", value=action_taken, inline=False)
    return embed


def build_indicator_text(domains: Iterable[str], amounts: Iterable[str], wallets: Iterable[str]) -> str:
    parts = []
    if domains:
        parts.append(f"domains={', '.join(str(domain) for domain in domains)}")
    if amounts:
        parts.append(f"amounts={', '.join(str(amount) for amount in amounts)}")
    if wallets:
        parts.append(f"wallets={', '.join(str(wallet) for wallet in wallets)}")
    return " | ".join(parts) if parts else "none"


def build_mod_files(images: Iterable[DownloadedImage]) -> list[discord.File]:
    return build_discord_files(images)

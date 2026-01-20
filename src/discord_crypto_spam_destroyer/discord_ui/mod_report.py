from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import discord

from discord_crypto_spam_destroyer.config import ActionHigh
from discord_crypto_spam_destroyer.hashes.store import FileHashStore
from discord_crypto_spam_destroyer.moderation.actions import apply_high_action
from discord_crypto_spam_destroyer.utils.image import DownloadedImage, build_discord_files


@dataclass(frozen=True)
class ReportContext:
    guild: discord.Guild
    channel: discord.TextChannel
    message: discord.Message
    author: discord.abc.User
    images: Iterable[DownloadedImage]
    action_high: ActionHigh
    hash_store: FileHashStore
    all_hashes: list[str]
    mod_role_id: int | None
    allow_hash_add: bool
    kick_disabled: bool


class ReportView(discord.ui.View):
    def __init__(
        self,
        context: ReportContext,
        timeout: float = 3600,
    ) -> None:
        super().__init__(timeout=timeout)
        self.context = context
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.label == "Kick":
                child.disabled = context.kick_disabled

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
        content = (
            interaction.message.content if interaction.message else ""
        )
        actor = interaction.user.mention if interaction.user else "Unknown"
        updated = f"{content}\n\nAction by {actor}: {result}" if content else f"Action by {actor}: {result}"
        if interaction.response.is_done():
            await interaction.edit_original_response(content=updated, view=self)
        else:
            await interaction.response.edit_message(content=updated, view=self)

    @discord.ui.button(label="Kick", style=discord.ButtonStyle.danger)
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
        success = await apply_high_action(
            self.context.guild,
            self.context.author.id,
            "kick",
            "Manual mod action from report",
        )
        result = "Kicked" if success else "Kick failed or user gone"
        await self._finalize_action(interaction, result)

    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger)
    async def ban_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not await self._ensure_permissions(interaction, "ban"):
            return
        success = await apply_high_action(
            self.context.guild,
            self.context.author.id,
            "ban",
            "Manual mod action from report",
        )
        result = "Banned" if success else "Ban failed or user gone"
        await self._finalize_action(interaction, result)

    @discord.ui.button(label="Ignore", style=discord.ButtonStyle.secondary)
    async def ignore_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await self._finalize_action(interaction, "Ignored")

    @discord.ui.button(label="Add Hashes", style=discord.ButtonStyle.primary)
    async def add_hash_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not await self._ensure_permissions(interaction, "kick"):
            return
        if not self.context.allow_hash_add:
            await self._finalize_action(interaction, "Hashes already known")
            return
        added = 0
        for phash in self.context.all_hashes:
            self.context.hash_store.add(phash)
            added += 1
        await self._finalize_action(interaction, f"Added {added} hashes")


def build_report_content(
    message: discord.Message,
    author: discord.abc.User,
    confidence: float,
    reasons: Iterable[str],
    indicators: str,
    action_suggestion: str,
    action_taken: str,
    author_roles: str,
) -> str:
    reason_text = ", ".join(reasons) if reasons else "none"
    return (
        f"**Possible crypto scam**\n"
        f"Author: {author.mention} ({author.id}) {author_roles}\n"
        f"Message: {message.jump_url}\n"
        f"Confidence: {confidence:.2f}\n"
        f"Reasons: {reason_text}\n"
        f"Indicators: {indicators}\n"
        f"Action taken: {action_taken}\n"
        f"Suggested: `{action_suggestion}`"
    )


def build_indicator_text(domains: Iterable[str], amounts: Iterable[str], wallets: Iterable[str]) -> str:
    parts = []
    if domains:
        parts.append(f"domains={', '.join(domains)}")
    if amounts:
        parts.append(f"amounts={', '.join(amounts)}")
    if wallets:
        parts.append(f"wallets={', '.join(wallets)}")
    return " | ".join(parts) if parts else "none"


def build_mod_files(images: Iterable[DownloadedImage]) -> list[discord.File]:
    return build_discord_files(images)

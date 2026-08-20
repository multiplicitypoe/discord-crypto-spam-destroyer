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


def hash_add_label(new_count: int) -> str:
    """What the add button says.

    Carrying the count means a moderator knows the size of what they are about
    to do before pressing it, rather than after.
    """
    if new_count == 1:
        return "Add 1 new hash"
    return f"Add {new_count} new hashes"


def suggested_next_step(new_hashes: int, needs_review: bool) -> str:
    """The one line telling a moderator what is actually left to do.

    The post is already deleted by the time any of these cards exist, so the
    only outstanding question is usually whether the denylist is missing
    anything. Saying "no action necessary" while images were still missing hid
    the one thing worth doing.
    """
    if new_hashes:
        images = "1 image" if new_hashes == 1 else f"{new_hashes} images"
        missing = f"{images} not on the denylist yet"
        if needs_review:
            return f"Check this is a scam, then add the {missing}"
        return f"Add the {missing}"
    if needs_review:
        return "Check this is a scam. Every image is already on the denylist"
    return "Nothing outstanding. Every image is already on the denylist"


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
    # How many of this post's images were new when the card was posted. None on
    # a card restored after a restart: the buttons it is already showing were
    # decided when it went up, and redrawing them all on every restart costs
    # more than it is worth.
    new_hashes: int | None = None


class ReportView(discord.ui.View):
    def __init__(
        self,
        context: ReportContext,
        timeout: float | None = None,
    ) -> None:
        super().__init__(timeout=timeout)
        self.context = context
        new_hashes = context.new_hashes
        for child in list(self.children):
            if not isinstance(child, discord.ui.Button):
                continue
            if child.label == "Kick":
                child.disabled = context.kick_disabled
            if child.custom_id == "report_add_hashes":
                # Nothing to add means no button at all, rather than a dead one
                # labelled after the reason it cannot be pressed. A restored
                # card has no count, so it keeps whatever it was posted with.
                if not context.allow_hash_add or new_hashes == 0:
                    self.remove_item(child)
                elif new_hashes:
                    child.label = hash_add_label(new_hashes)

    async def _ensure_mod_or_kick_or_ban(self, interaction: discord.Interaction) -> bool:
        if not interaction.user or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Permissions check failed.", ephemeral=True)
            return False
        if self.context.mod_role_id:
            if any(role.id == self.context.mod_role_id for role in interaction.user.roles):
                return True
            if interaction.user.guild_permissions.kick_members or interaction.user.guild_permissions.ban_members:
                return True
            await interaction.response.send_message(
                "Missing Mod role or kick/ban permission.", ephemeral=True
            )
            return False
        if interaction.user.guild_permissions.kick_members or interaction.user.guild_permissions.ban_members:
            return True
        await interaction.response.send_message("Missing kick/ban permission.", ephemeral=True)
        return False

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
        if not await self._ensure_mod_or_kick_or_ban(interaction):
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
        if not await self._ensure_mod_or_kick_or_ban(interaction):
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
        label="Dismiss",
        style=discord.ButtonStyle.secondary,
        custom_id="report_ignore",
    )
    async def ignore_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        """Close the card without adding anything.

        Named for what the moderator is doing rather than for the advice, which
        is what "No action necessary" was: a button with the same words as the
        suggestion above it.
        """
        if not await self._ensure_mod_or_kick_or_ban(interaction):
            return
        logger.info("Mod action: dismissed by %s", interaction.user)
        await self._finalize_action(interaction, "Dismissed")

    @discord.ui.button(label="Add hashes", style=discord.ButtonStyle.primary,
                       custom_id="report_add_hashes")
    async def add_hash_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not await self._ensure_mod_or_kick_or_ban(interaction):
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
        value=f"{author.mention} ({author}, {author.id}) {author_roles}",
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

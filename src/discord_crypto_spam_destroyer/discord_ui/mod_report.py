"""The report card a moderator sees after the bot acts on a post.

It is an informative card built with Discord's components v2: what was removed,
how fast, why, and the images. The only button is "Add hashes", shown when some
of the post's images are not on the denylist yet. Moderators pressed it about
160 times in seven months. Kick and Ban were never pressed in 933 cards, and
Dismiss only ever marked a card that had nothing left to do, so they are gone.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Sequence

import discord
from discord import ui

from discord_crypto_spam_destroyer.discord_ui.report_store import ReportRecord, ReportStore
from discord_crypto_spam_destroyer.hashes.store import FileHashStore
from discord_crypto_spam_destroyer.utils.image import DownloadedImage

logger = logging.getLogger("discord_crypto_spam_destroyer")

ADD_HASHES_ID = "report_add_hashes"
# Buttons on the older embed cards, stripped from them when the bot restarts.
RETIRED_BUTTON_IDS = frozenset({"report_kick", "report_ban", "report_ignore"})

ACCENT_REMOVED = discord.Colour.red()
ACCENT_REVIEW = discord.Colour.orange()


def hash_add_label(new_count: int) -> str:
    """What the add button says, with the count, so a moderator knows the size first."""
    if new_count == 1:
        return "Add 1 new hash"
    return f"Add {new_count} new hashes"


def suggested_next_step(new_hashes: int, needs_review: bool) -> str | None:
    """What is left for a moderator to do, or None when nothing is."""
    if new_hashes:
        missing = (
            "the 1 image that isn't on the denylist yet"
            if new_hashes == 1
            else f"the {new_hashes} images that aren't on the denylist yet"
        )
        if needs_review:
            return f"Check this is a scam, then add {missing}"
        return f"Add {missing}"
    if needs_review:
        return "Check this is a scam. Every image is already on the denylist"
    return None


_ACTIONS = {
    "softban": "author softbanned",
    "ban": "author banned",
    "kick": "author kicked",
    "report_only": "reported only",
    "report only": "reported only",
    "report only (allowlisted)": "reported only (allowlisted)",
    "no kick (author is Mod)": "author is a mod, not actioned",
    "kick failed": "action on the author failed",
}


def describe_action(action_result: str | None) -> str | None:
    if not action_result:
        return None
    if action_result.endswith("(cooldown)"):
        return "author already actioned for an earlier post"
    return _ACTIONS.get(action_result, action_result)


def describe_outcome(deleted: bool, removed_after_s: float | None, action_result: str | None) -> str:
    if deleted and removed_after_s is not None:
        head = f"Removed **{removed_after_s:.2f}s** after it was posted"
    elif deleted:
        head = "Removed"
    else:
        head = "**Not removed**"
    action = describe_action(action_result)
    return f"{head} · {action}" if action else head


def build_indicator_text(
    domains: Iterable[str], amounts: Iterable[str], wallets: Iterable[str]
) -> str | None:
    parts = []
    if domains:
        parts.append(f"domains {', '.join(str(d) for d in domains)}")
    if amounts:
        parts.append(f"amounts {', '.join(str(a) for a in amounts)}")
    if wallets:
        parts.append(f"wallets {', '.join(str(w) for w in wallets)}")
    return " · ".join(parts) if parts else None


def card_text(
    message: discord.Message,
    author: discord.abc.User,
    author_roles: str,
    *,
    reason: str,
    indicators: str | None,
    suggestion: str | None,
    outcome: str,
    deleted: bool,
    needs_review: bool,
) -> dict:
    """Everything the card says, as plain data, so it can be stored and redrawn."""
    roles = author_roles.strip().removeprefix("(").removesuffix(")")
    channel = getattr(message.channel, "mention", "#unknown")
    avatar = getattr(getattr(author, "display_avatar", None), "url", None)
    return {
        "title": "Crypto scam removed" if deleted else "Possible crypto scam",
        "message_url": message.jump_url,
        "author_line": f"{author.mention} · {author.name} · `{author.id}`",
        "roles": roles,
        "avatar_url": avatar,
        "outcome": outcome,
        "reason": reason,
        "indicators": indicators,
        "suggestion": suggestion,
        "footer": f"Posted in {channel} {discord.utils.format_dt(message.created_at, 'f')}",
        "needs_review": needs_review,
    }


def attachment_names(images: Sequence[DownloadedImage]) -> list[str]:
    """Unique names, since a gallery points at attachments by name and scam posts reuse image.png."""
    names = []
    for index, image in enumerate(images, start=1):
        extension = (image.filename.rsplit(".", 1)[-1] if "." in image.filename else "png").lower()
        names.append(f"image_{index}.{extension}")
    return names


def build_files(images: Sequence[DownloadedImage]) -> list[discord.File]:
    from io import BytesIO

    return [
        discord.File(fp=BytesIO(image.data), filename=name)
        for image, name in zip(images, attachment_names(images))
    ]


@dataclass
class HashActions:
    """What the Add hashes button needs to do its job and redraw the card."""

    hash_store: FileHashStore
    all_hashes: list[str]
    mod_role_id: int | None
    report_store: ReportStore
    record: ReportRecord | None = None
    new_hashes: int | None = None


class ReportCard(ui.LayoutView):
    def __init__(
        self,
        card: dict,
        image_urls: Sequence[str],
        actions: HashActions | None = None,
        note: str | None = None,
    ) -> None:
        super().__init__(timeout=None)
        self.card = card
        self.actions = actions

        heading = f"### [{card['title']}]({card['message_url']})\n{card['author_line']}"
        if card.get("roles"):
            heading += f"\n-# {card['roles']}"
        if card.get("avatar_url"):
            header: ui.Item = ui.Section(ui.TextDisplay(heading), accessory=ui.Thumbnail(card["avatar_url"]))
        else:
            header = ui.TextDisplay(heading)

        body = [card["outcome"], card["reason"]]
        if card.get("indicators"):
            body.append(f"-# {card['indicators']}")
        children: list[ui.Item] = [header, ui.TextDisplay("\n".join(body))]
        if image_urls:
            children.append(ui.MediaGallery(*(discord.MediaGalleryItem(url) for url in image_urls[:10])))
        children.append(ui.TextDisplay(f"-# {card['footer']}"))

        if note:
            children.append(ui.Separator())
            children.append(ui.TextDisplay(note))
        elif card.get("suggestion"):
            children.append(ui.Separator())
            children.append(ui.TextDisplay(f"**To do:** {card['suggestion']}"))
            if actions is not None and actions.new_hashes != 0:
                label = hash_add_label(actions.new_hashes) if actions.new_hashes else "Add hashes"
                button: ui.Button = ui.Button(
                    label=label, style=discord.ButtonStyle.primary, custom_id=ADD_HASHES_ID
                )
                button.callback = self._add_hashes
                children.append(ui.ActionRow(button))

        accent = ACCENT_REVIEW if card.get("needs_review") else ACCENT_REMOVED
        self.add_item(ui.Container(*children, accent_colour=accent))

    @property
    def has_button(self) -> bool:
        return any(getattr(item, "custom_id", None) == ADD_HASHES_ID for item in self.walk_children())

    async def _add_hashes(self, interaction: discord.Interaction) -> None:
        if self.actions is None or not await _is_mod(interaction, self.actions.mod_role_id):
            return
        result = add_new_hashes(self.actions, interaction.user)
        image_urls = gallery_urls(interaction.message) if interaction.message else []
        actor = interaction.user.mention if interaction.user else "Someone"
        redrawn = ReportCard(self.card, image_urls, note=f"-# {actor}: {result}")
        await interaction.response.edit_message(view=redrawn)
        if self.actions.record is not None:
            self.actions.report_store.delete_report(self.actions.record.message_id)
        self.stop()


class LegacyReportView(discord.ui.View):
    """Keeps Add hashes working on embed cards posted before the redesign.

    Those cards age out of the report store after a week; then this can go.
    """

    def __init__(self, actions: HashActions) -> None:
        super().__init__(timeout=None)
        self.actions = actions

    @discord.ui.button(label="Add hashes", style=discord.ButtonStyle.primary, custom_id=ADD_HASHES_ID)
    async def add_hash_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await _is_mod(interaction, self.actions.mod_role_id):
            return
        result = add_new_hashes(self.actions, interaction.user)
        actor = interaction.user.mention if interaction.user else "Someone"
        embed = interaction.message.embeds[0] if interaction.message and interaction.message.embeds else None
        if embed is not None:
            embed.add_field(name="Action taken", value=f"Action by {actor}: {result}", inline=False)
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            await interaction.response.edit_message(view=None)
        if self.actions.record is not None:
            self.actions.report_store.delete_report(self.actions.record.message_id)
        self.stop()


def gallery_urls(message: discord.Message) -> list[str]:
    """The image URLs a card shows.

    A components v2 message folds its uploads into the gallery, so
    message.attachments comes back empty. The URLs are signed, and a message
    fetched for an interaction carries fresh ones.
    """
    urls: list[str] = []

    def walk(components) -> None:
        for component in components or []:
            if isinstance(component, discord.MediaGalleryComponent):
                urls.extend(item.media.url for item in component.items)
            walk(getattr(component, "children", None) or getattr(component, "components", None))

    walk(message.components)
    return urls or [attachment.url for attachment in message.attachments]


def add_new_hashes(actions: HashActions, user: object) -> str:
    existing = actions.hash_store.load()
    new_hashes = list(dict.fromkeys(p for p in actions.all_hashes if p not in existing))
    if not new_hashes:
        logger.info("Mod action: add hashes pressed by %s (no-op)", user)
        return "every image was already on the denylist"
    for phash in new_hashes:
        actions.hash_store.add(phash)
    logger.info("Mod action: add hashes pressed by %s (%s added)", user, len(new_hashes))
    return f"added {len(new_hashes)} {'hash' if len(new_hashes) == 1 else 'hashes'} to the denylist"


async def _is_mod(interaction: discord.Interaction, mod_role_id: int | None) -> bool:
    user = interaction.user
    if not isinstance(user, discord.Member):
        await interaction.response.send_message("Permissions check failed.", ephemeral=True)
        return False
    if mod_role_id and any(role.id == mod_role_id for role in user.roles):
        return True
    if user.guild_permissions.kick_members or user.guild_permissions.ban_members:
        return True
    await interaction.response.send_message("Missing Mod role or kick/ban permission.", ephemeral=True)
    return False

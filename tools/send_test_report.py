from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import discord

try:
    from discord_crypto_spam_destroyer.config import load_settings, resolve_settings
    from discord_crypto_spam_destroyer.discord_ui.mod_report import (
        ReportContext,
        ReportView,
        build_report_embed,
    )
    from discord_crypto_spam_destroyer.discord_ui.report_store import ReportStore
    from discord_crypto_spam_destroyer.hashes.store import FileHashStore
except ModuleNotFoundError:
    sys.path.append(str(Path("src").resolve()))
    from discord_crypto_spam_destroyer.config import load_settings, resolve_settings
    from discord_crypto_spam_destroyer.discord_ui.mod_report import (
        ReportContext,
        ReportView,
        build_report_embed,
    )
    from discord_crypto_spam_destroyer.discord_ui.report_store import ReportStore
    from discord_crypto_spam_destroyer.hashes.store import FileHashStore

@dataclass(frozen=True)
class TargetInfo:
    guild: discord.Guild
    channel: discord.TextChannel
    author: discord.abc.User
    mod_role_id: int | None




class TestReportBot(discord.Client):
    def __init__(self, token: str) -> None:
        intents = discord.Intents.default()
        intents.guilds = True
        super().__init__(intents=intents)
        self.token = token

    async def on_ready(self) -> None:
        target = await resolve_target(self)
        if not target:
            await self.close()
            return

        last_message = target.channel.last_message
        if last_message is None:
            history = [message async for message in target.channel.history(limit=1)]
            last_message = history[0] if history else None
        if last_message is None:
            last_message = await target.channel.send("Test report baseline message.")

        context = ReportContext(
            guild=target.guild,
            channel=target.channel,
            message=last_message,
            author=target.author,
            images=[],
            hash_store=FileHashStore(Path("data") / "bad_hashes.txt"),
            all_hashes=[],
            mod_role_id=target.mod_role_id,
            allow_hash_add=True,
            kick_disabled=False,
            report_store=ReportStore(Path("data") / "report_store.json"),
            report_record=None,
        )

        embed = build_report_embed(
            last_message,
            target.author,
            confidence=0.75,
            reasons=["Test report"],
            indicators="none",
            action_suggestion="/kick USER_ID",
            action_taken="none",
            author_roles="(test roles)",
        )

        view = ReportView(context)
        await target.channel.send(embed=embed, view=view)
        await self.close()

    def run_bot(self) -> None:
        self.run(self.token)


async def resolve_target(client: discord.Client) -> TargetInfo | None:
    settings = load_settings()
    guild_id = os.getenv("GUILD_ID")
    target_user_id = os.getenv("TEST_TARGET_ID")

    guild: discord.Guild | None = None
    if guild_id:
        guild = client.get_guild(int(guild_id))
    if guild is None and client.guilds:
        guild = client.guilds[0]
    if guild is None:
        return None

    resolved = resolve_settings(settings, guild.id)
    mod_channel = resolved.mod_channel
    if not mod_channel:
        raise SystemExit("MOD_CHANNEL not set")

    channel: discord.TextChannel | None = None
    if mod_channel.isdigit():
        resolved_channel = guild.get_channel(int(mod_channel))
        if isinstance(resolved_channel, discord.TextChannel):
            channel = resolved_channel
    else:
        for text_channel in guild.text_channels:
            if text_channel.name == mod_channel:
                channel = text_channel
                break
    if channel is None:
        return None

    author: discord.abc.User | None = None
    if target_user_id:
        author = guild.get_member(int(target_user_id))
    if author is None:
        author = guild.me
    if author is None and guild.members:
        author = guild.members[0]
    if author is None:
        author = client.user
    if author is None:
        return None

    return TargetInfo(
        guild=guild,
        channel=channel,
        author=author,
        mod_role_id=resolved.mod_role_id,
    )


def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN not set")
    bot = TestReportBot(token)
    bot.run_bot()


if __name__ == "__main__":
    main()

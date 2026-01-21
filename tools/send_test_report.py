from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import discord

try:
    from discord_crypto_spam_destroyer.discord_ui.mod_report import (
        ReportContext,
        ReportView,
        build_report_embed,
    )
    from discord_crypto_spam_destroyer.hashes.store import FileHashStore
except ModuleNotFoundError:
    sys.path.append(str(Path("src").resolve()))
    from discord_crypto_spam_destroyer.discord_ui.mod_report import (
        ReportContext,
        ReportView,
        build_report_embed,
    )
    from discord_crypto_spam_destroyer.hashes.store import FileHashStore

MOD_CHANNEL_ENV = "MOD_CHANNEL"


@dataclass(frozen=True)
class TargetInfo:
    guild: discord.Guild
    channel: discord.TextChannel
    author: discord.abc.User


class NoopReportStore:
    def delete_report(self, message_id: int) -> None:
        return


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

        mod_role_value = os.getenv("MOD_ROLE_ID")
        mod_role_id = int(mod_role_value) if mod_role_value else None
        context = ReportContext(
            guild=target.guild,
            channel=target.channel,
            message=last_message,
            author=target.author,
            images=[],
            hash_store=FileHashStore(Path("data") / "bad_hashes.txt"),
            all_hashes=[],
            mod_role_id=mod_role_id,
            allow_hash_add=True,
            kick_disabled=False,
            report_store=NoopReportStore(),
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
    guild_id = os.getenv("GUILD_ID")
    mod_channel = os.getenv(MOD_CHANNEL_ENV)
    if not mod_channel:
        raise SystemExit("MOD_CHANNEL not set")
    target_user_id = os.getenv("TEST_TARGET_ID")

    guild: discord.Guild | None = None
    if guild_id:
        guild = client.get_guild(int(guild_id))
    if guild is None and client.guilds:
        guild = client.guilds[0]
    if guild is None:
        return None

    channel: discord.TextChannel | None = None
    if mod_channel.isdigit():
        resolved = guild.get_channel(int(mod_channel))
        if isinstance(resolved, discord.TextChannel):
            channel = resolved
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

    return TargetInfo(guild=guild, channel=channel, author=author)


def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN not set")
    bot = TestReportBot(token)
    bot.run_bot()


if __name__ == "__main__":
    main()

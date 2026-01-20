from __future__ import annotations

from typing import Literal

import discord

ActionHigh = Literal["kick", "ban", "report_only", "softban"]


async def safe_delete(message: discord.Message) -> bool:
    try:
        await message.delete()
        return True
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return False


def _resolve_member(guild: discord.Guild, user_id: int) -> discord.Member | None:
    member = guild.get_member(user_id)
    if member is None:
        return None
    return member


async def safe_kick(guild: discord.Guild, user_id: int, reason: str) -> bool:
    member = _resolve_member(guild, user_id)
    if member is None:
        return False
    try:
        await guild.kick(member, reason=reason)
        return True
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return False


async def safe_unban(guild: discord.Guild, user_id: int, reason: str) -> bool:
    try:
        await guild.unban(discord.Object(id=user_id), reason=reason)
        return True
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return False


async def safe_ban(guild: discord.Guild, user_id: int, reason: str, delete_days: int | None = None) -> bool:
    target = guild.get_member(user_id) or discord.Object(id=user_id)
    try:
        if delete_days is not None:
            await guild.ban(target, reason=reason, delete_message_days=delete_days)
        else:
            await guild.ban(target, reason=reason)
        return True
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return False


async def apply_high_action(
    guild: discord.Guild,
    user_id: int,
    action: ActionHigh,
    reason: str,
    softban_delete_days: int = 1,
) -> bool:
    if action == "report_only":
        return True
    if action == "softban":
        if not await safe_ban(guild, user_id, reason, delete_days=softban_delete_days):
            return False
        return await safe_unban(guild, user_id, reason)
    if action == "ban":
        return await safe_ban(guild, user_id, reason)
    return await safe_kick(guild, user_id, reason)

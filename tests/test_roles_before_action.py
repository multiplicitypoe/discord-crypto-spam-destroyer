"""Roles must be read off the author before any kick/ban/softban runs.

The known-bad-hash-match path deleted the message, applied the high-confidence
action (kick/ban/softban), and only then looked up the author's roles for the
report card. A softban removes the member from the guild, so by the time the
lookup ran the member was already gone and Discord's REST API genuinely has
nothing to return -- "(roles unknown)" was correct given when it asked, but it
asked too late. The vision-classified path already gets this right by looking
the roles up before acting; the hash-match path did not.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from discord_crypto_spam_destroyer.bot import CryptoSpamBot  # noqa: E402


def test_roles_are_captured_before_the_action_can_remove_the_member():
    calls = []

    async def delete():
        calls.append("delete")
        return True

    async def capture_roles():
        calls.append("roles")
        return "(Verified)"

    async def act():
        calls.append("act")
        return "softban"

    result = asyncio.run(
        CryptoSpamBot._delete_capture_roles_then_act(
            object(), delete=delete, capture_roles=capture_roles, act=act
        )
    )

    assert calls == ["delete", "roles", "act"], calls
    assert result == (True, "(Verified)", "softban")

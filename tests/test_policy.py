from discord_crypto_spam_destroyer.config import ActionHigh, ActionMedium


def test_action_types() -> None:
    high: ActionHigh = "kick"
    medium: ActionMedium = "delete_only"
    assert high == "kick"
    assert medium == "delete_only"

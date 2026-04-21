from discord_crypto_spam_destroyer.moderation.whitelist import is_channel_in_list

ALLOWLIST = (100, 200, 300)


def test_direct_channel_match() -> None:
    assert is_channel_in_list(100, parent_id=None, category_id=None, id_list=ALLOWLIST) == 100


def test_thread_inherits_from_parent() -> None:
    assert is_channel_in_list(999, parent_id=200, category_id=50, id_list=ALLOWLIST) == 200


def test_channel_inherits_from_category() -> None:
    assert is_channel_in_list(999, parent_id=None, category_id=300, id_list=ALLOWLIST) == 300


def test_thread_inherits_from_category() -> None:
    # Thread 999, parent 888 (not listed), category 300
    assert is_channel_in_list(999, parent_id=888, category_id=300, id_list=ALLOWLIST) == 300


def test_no_match() -> None:
    assert is_channel_in_list(999, parent_id=888, category_id=777, id_list=ALLOWLIST) is None


def test_no_match_no_parents() -> None:
    assert is_channel_in_list(999, parent_id=None, category_id=None, id_list=ALLOWLIST) is None


def test_empty_list() -> None:
    assert is_channel_in_list(100, parent_id=None, category_id=None, id_list=()) is None


def test_priority_channel_over_parent() -> None:
    assert is_channel_in_list(100, parent_id=200, category_id=300, id_list=ALLOWLIST) == 100


def test_priority_parent_over_category() -> None:
    assert is_channel_in_list(999, parent_id=200, category_id=300, id_list=ALLOWLIST) == 200

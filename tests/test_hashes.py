from discord_crypto_spam_destroyer.hashes.store import match_hashes


def test_match_hashes() -> None:
    known = {"abc", "def"}
    result = match_hashes(["abc", "zzz"], known)
    assert result.matched is True
    assert result.matched_hashes == ["abc"]


def test_match_hashes_no_match() -> None:
    known = {"abc"}
    result = match_hashes(["zzz"], known)
    assert result.matched is False
    assert result.matched_hashes == []

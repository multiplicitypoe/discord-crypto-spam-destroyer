"""A flagged post is caught on one image, but it carries several.

Matching is any-of, so one known image is enough to act on the post. The others
are usually not on the list yet, and recording only the matched one leaves the
rest of that post unrecorded, so a moderator needs to be able to add them.
"""
from discord_crypto_spam_destroyer.hashes.store import match_hashes

KNOWN = "f0e1d2c3b4a59687"
OTHER_KNOWN = "0f1e2d3c4b5a6978"
NEW_ONE = "1234567890abcdef"
NEW_TWO = "fedcba0987654321"
WHITE = "8000000000000000"


def test_a_partial_match_reports_the_images_still_unknown():
    match = match_hashes([KNOWN, NEW_ONE, NEW_TWO], {KNOWN})
    assert match.matched is True
    assert list(match.matched_hashes) == [KNOWN]
    assert list(match.unmatched_hashes) == [NEW_ONE, NEW_TWO]


def test_nothing_is_left_over_when_every_image_is_known():
    match = match_hashes([KNOWN, OTHER_KNOWN], {KNOWN, OTHER_KNOWN})
    assert match.matched is True
    assert list(match.unmatched_hashes) == []


def test_a_blank_image_is_never_offered_as_something_to_add():
    """The store refuses degenerate hashes, so offering them would mislead."""
    match = match_hashes([KNOWN, WHITE], {KNOWN})
    assert list(match.unmatched_hashes) == []


def test_unknown_images_are_reported_even_when_nothing_matched():
    match = match_hashes([NEW_ONE, NEW_TWO], {KNOWN})
    assert match.matched is False
    assert list(match.unmatched_hashes) == [NEW_ONE, NEW_TWO]


def test_a_repeated_image_is_only_offered_once():
    match = match_hashes([KNOWN, NEW_ONE, NEW_ONE], {KNOWN})
    assert list(match.unmatched_hashes) == [NEW_ONE]

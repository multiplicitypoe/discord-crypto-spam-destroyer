"""The card should say what is left to do, and offer only the buttons for it.

It used to say "No action necessary" as the suggestion on a post that still had
images missing from the denylist, and then offer a button also called "No action
necessary". So the one thing worth doing went unmentioned, and the button that
did nothing was named after the advice.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from discord_crypto_spam_destroyer.discord_ui.mod_report import (  # noqa: E402
    hash_add_label,
    suggested_next_step,
)


class TheButtonSaysHowMuchItWillDo(unittest.TestCase):
    def test_one_hash_is_singular(self):
        self.assertEqual(hash_add_label(1), "Add 1 new hash")

    def test_several_hashes_carry_the_count(self):
        self.assertEqual(hash_add_label(3), "Add 3 new hashes")


class TheSuggestionSaysWhatIsLeft(unittest.TestCase):
    def test_new_images_are_the_thing_to_do(self):
        text = suggested_next_step(new_hashes=3, needs_review=False)
        self.assertIn("3", text)
        self.assertIn("denylist", text)

    def test_one_new_image_reads_singular(self):
        text = suggested_next_step(new_hashes=1, needs_review=False)
        self.assertIn("1 image", text)
        self.assertNotIn("images", text)

    def test_nothing_left_says_so_plainly(self):
        text = suggested_next_step(new_hashes=0, needs_review=False)
        self.assertNotIn("denylist yet", text)
        self.assertIn("Nothing", text)

    def test_a_post_needing_a_look_asks_for_one_first(self):
        text = suggested_next_step(new_hashes=2, needs_review=True)
        self.assertIn("scam", text.lower())
        self.assertIn("2", text)

    def test_a_post_needing_a_look_with_nothing_to_add_still_asks(self):
        text = suggested_next_step(new_hashes=0, needs_review=True)
        self.assertIn("scam", text.lower())

    def test_the_old_wording_is_gone(self):
        """It was the suggestion on cards that still had work outstanding."""
        for new_hashes in (0, 1, 5):
            for needs_review in (False, True):
                self.assertNotIn(
                    "no action necessary",
                    suggested_next_step(new_hashes, needs_review).lower(),
                )


if __name__ == "__main__":
    unittest.main()

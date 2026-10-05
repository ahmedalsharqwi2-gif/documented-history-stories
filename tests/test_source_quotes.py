import unittest

from scripts.source_integrity_gate import undocumented_quotes


class SourceQuoteTests(unittest.TestCase):
    def test_verified_name_label_is_not_dialogue(self):
        episode = {"narration": "كان «نُبُونَيْدُ» ملكًا.",
                   "historical_verification_report": {"main_figures": ["نبونيد ملك بابل"]}}
        self.assertEqual(undocumented_quotes(episode), [])

    def test_dialogue_and_unlisted_names_still_require_source_location(self):
        episode = {"narration": 'قال «سنعود غدًا» إلى "سليم".',
                   "historical_verification_report": {"main_figures": ["نبونيد"]}}
        self.assertEqual(undocumented_quotes(episode), ["سنعود غدًا", "سليم"])

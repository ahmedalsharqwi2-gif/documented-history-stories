"""Regression tests for the pre-TTS Arabic narration validator."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from arabic_guard import Issue, validate_narration  # noqa: E402


class ArabicGuardTests(unittest.TestCase):
    def test_valid_arabic_narration_has_no_issues(self):
        issues = validate_narration("السلام عليكم ورحمة الله وبركاته")
        self.assertEqual(issues, [])

    def test_foreign_script_and_digits_are_reported(self):
        issues = validate_narration("في 14 أغسطس carrying a crew")
        kinds = {issue.kind for issue in issues}
        self.assertIn("foreign_script", kinds)
        self.assertIn("digit", kinds)
        self.assertTrue(all(isinstance(issue, Issue) for issue in issues))

    def test_low_arabic_ratio_is_reported(self):
        issues = validate_narration("hello مرحبا")
        self.assertIn("low_arabic_ratio", {issue.kind for issue in issues})


if __name__ == "__main__":
    unittest.main()

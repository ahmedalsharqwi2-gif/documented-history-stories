"""Test cases for Arabic text validation."""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.arabic_guard import validate_narration


class TestArabicGuard(unittest.TestCase):
    
    def test_valid_arabic_narration(self):
        """Test that valid Arabic text passes validation."""
        text = "السلام عليكم ورحمة الله وبركاته"
        issues = validate_narration(text)
        self.assertEqual(len(issues), 0)
    
if __name__ == "__main__":
    unittest.main()

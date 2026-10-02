"""Test cases for Arabic text validation."""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.arabic_guard import validate_hook, validate_narration


class TestArabicGuard(unittest.TestCase):
    
    def test_valid_arabic_narration(self):
        """Test that valid Arabic text passes validation."""
        text = "السلام عليكم ورحمة الله وبركاته"
        issues = validate_narration(text)
        self.assertEqual(len(issues), 0)

    def test_editorial_labels_never_reach_narration(self):
        """Planning vocabulary must be rejected from the spoken track."""
        text = "الخطاف: هل تغيرت النتيجة؟ ثم نصل إلى العبرة في النهاية."
        issues = validate_narration(text)
        self.assertIn("internal_narration_label", {issue.kind for issue in issues})

    def test_all_internal_labels_are_blocked(self):
        for label in ("الحلقة المفتوحة", "المفارقة", "التصاعد", "الذروة", "الخاتمة"):
            with self.subTest(label=label):
                issues = validate_narration(f"بدأت القصة، {label}: ثم تتابعت الأحداث.")
                self.assertTrue(any(issue.kind == "internal_narration_label" for issue in issues))

    def test_hook_must_be_the_first_sentence_and_reasonably_long(self):
        hook = "كيف انتصر جيش قليل على قوة أكبر منه في معركة حاسمة؟"
        narration = hook + " ثم بدأت الأحداث التي كشفت سر هذا التحول."
        self.assertEqual(validate_hook(hook, narration), [])

    def test_generic_or_mismatched_hook_is_rejected(self):
        hook = "في هذا الفيديو سنتحدث اليوم عن قصة تاريخية مهمة"
        narration = "بدأت المعركة قبل شروق الشمس، ثم تغير كل شيء."
        kinds = {issue.kind for issue in validate_hook(hook, narration)}
        self.assertIn("generic_hook", kinds)
        self.assertIn("hook_not_first_sentence", kinds)
    
if __name__ == "__main__":
    unittest.main()

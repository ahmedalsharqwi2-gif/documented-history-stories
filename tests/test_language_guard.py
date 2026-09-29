import unittest

from scripts.language_guard import find_non_arabic_letters, validate_phonetic_hints


def strip_arabic_marks(text):
    return "".join(ch for ch in text if not ("\u064b" <= ch <= "\u065f" or ch == "\u0670"))


class LanguageGuardTests(unittest.TestCase):
    def test_arabic_diacritics_and_punctuation_are_allowed(self):
        self.assertEqual(find_non_arabic_letters("رَبَّنَا آتِنَا، علمًا."), [])

    def test_non_arabic_scripts_are_detected(self):
        for fragment in ("waveform", "extérieure", "entonces", "חזרה", "这一次", "ループ"):
            with self.subTest(fragment=fragment):
                self.assertTrue(find_non_arabic_letters(fragment))

    def test_valid_hint_is_safe_for_tts(self):
        validate_phonetic_hints(
            "تساءل الفريقُ.",
            [{"word": "تساءل الفريق", "phonetic": "تَسَاءَلَ الْفَرِيقُ"}],
            strip_arabic_marks,
        )

    def test_hint_with_latin_letters_or_changed_base_letters_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "غير عربية"):
            validate_phonetic_hints(
                "الحملة.", [{"word": "الحملة", "phonetic": "al-hamla"}], strip_arabic_marks
            )
        with self.assertRaisesRegex(ValueError, "يضيف التشكيل فقط"):
            validate_phonetic_hints(
                "الحملة.", [{"word": "الحملة", "phonetic": "الحَمْلَة".replace("ح", "ه", 1)}], strip_arabic_marks
            )

    def test_hint_not_found_in_narration_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "غير موجودة في narration"):
            validate_phonetic_hints(
                "الحملة.", [{"word": "المعركة", "phonetic": "الْمَعْرَكَة"}], strip_arabic_marks
            )


if __name__ == "__main__":
    unittest.main()

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from arabic_pronunciation import (
    apply_pronunciation_dictionary,
    load_pronunciation_dictionary,
    mantoq_vocalize,
    prepare_tts_text,
    strip_marks,
)


class ArabicPronunciationTests(unittest.TestCase):
    def test_dictionary_loads_and_replaces_longest_phrase_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pronunciation.json"
            path.write_text(json.dumps({"قلبه": {"spoken": "قَلْبُهُ"}}, ensure_ascii=False), encoding="utf-8")
            mapping = load_pronunciation_dictionary(path)
            output = apply_pronunciation_dictionary("حفظ قلبه في القاهرة", mapping)
        self.assertIn("قَلْبُهُ", output)
        self.assertEqual(strip_marks(output).split(), "حفظ قلبه في القاهرة".split())

    def test_dictionary_does_not_replace_inside_another_word(self):
        mapping = {"عدة": "عِدَّة"}
        output = apply_pronunciation_dictionary("عدة معدات", mapping)
        self.assertEqual(output, "عِدَّة معدات")

    @patch.dict(os.environ, {"MANTOQ_REQUIRED": "false"}, clear=False)
    def test_mantoq_is_optional_when_not_installed(self):
        text, phonemes = mantoq_vocalize("نص عربي")
        self.assertEqual(text, "نص عربي")
        self.assertEqual(phonemes, [])

    def test_prepare_tts_rejects_word_sequence_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pronunciation.json"
            path.write_text(json.dumps({"القاهرة": {"spoken": "دِمَشْقُ"}}, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(ValueError):
                prepare_tts_text("زار القاهرة", path)


if __name__ == "__main__":
    unittest.main()

import sys
import types
import unittest
from pathlib import Path

sys.modules.setdefault("edge_tts", types.ModuleType("edge_tts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from scripts.generate_voice import two_lines_ar, validate_caption_chunks


class CaptionLayoutTests(unittest.TestCase):
    def test_six_words_split_three_and_three(self):
        rendered = two_lines_ar(["واحد", "اثنان", "ثلاثة", "أربعة", "خمسة", "ستة"])
        self.assertIn(r"\N", rendered)
        self.assertIn("واحد اثنان ثلاثة", rendered)
        self.assertIn("أربعة خمسة ستة", rendered)

    def test_three_words_use_one_line(self):
        self.assertNotIn(r"\N", two_lines_ar(["واحد", "اثنان", "ثلاثة"]))

    def test_caption_guard_accepts_short_chunks(self):
        ass = "Dialogue: 0,0:00:00.00,0:00:02.00,Caption,,0,0,0,,واحد اثنان ثلاثة\\Nأربعة خمسة ستة"
        validate_caption_chunks(ass, max_words=6)

    def test_caption_guard_rejects_full_narration_event(self):
        ass = "Dialogue: 0,0:00:00.00,0:00:20.00,Caption,,0,0,0,," + " ".join(["كلمة"] * 40)
        with self.assertRaises(RuntimeError):
            validate_caption_chunks(ass, max_words=6)


if __name__ == "__main__":
    unittest.main()

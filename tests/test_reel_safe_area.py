import sys
import types
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.modules.setdefault("edge_tts", types.ModuleType("edge_tts"))

import assemble_video  # noqa: E402
import generate_voice  # noqa: E402


class ReelSafeAreaTests(unittest.TestCase):
    def test_narration_captions_use_top_safe_lane(self):
        style = next(line for line in generate_voice.build_ass_header().splitlines() if line.startswith("Style: Caption,"))
        self.assertIn(",8,70,70,160,1", style)

    def test_cta_is_in_a_separate_top_safe_lane_below_captions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cta.ass"
            assemble_video.write_cta_ass(path, 0.0, 4.0, "رسالة الريل")
            style = next(line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("Style: CTA,"))
        self.assertIn(",8,70,70,620,1", style)


if __name__ == "__main__":
    unittest.main()

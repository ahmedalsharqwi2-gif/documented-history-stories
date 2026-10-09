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
    def test_narration_captions_use_bottom_safe_lane_for_horizontal_master(self):
        style = next(line for line in generate_voice.build_ass_header().splitlines() if line.startswith("Style: Caption,"))
        self.assertIn(",2,70,70,70,1", style)

    def test_vertical_narration_captions_move_to_top_safe_lane(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "horizontal.ass"
            output = Path(directory) / "vertical.ass"
            source.write_text(generate_voice.build_ass_header(), encoding="utf-8")
            assemble_video.make_vertical_subtitles(source, output)
            style = next(line for line in output.read_text(encoding="utf-8").splitlines() if line.startswith("Style: Caption,"))
        self.assertIn(",8,70,70,300,1", style)

if __name__ == "__main__":
    unittest.main()

import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.modules.setdefault("edge_tts", types.ModuleType("edge_tts"))

import assemble_video  # noqa: E402
import generate_voice  # noqa: E402
from reel_subtitles import write_reel_subtitles  # noqa: E402


ASS_SOURCE = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Noto Sans Arabic,58,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,3,0,2,70,70,90,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:02.00,Caption,,0,0,0,,السطر الأول
Dialogue: 0,0:00:02.00,0:00:05.00,Caption,,0,0,0,,السطر الثاني
Dialogue: 0,0:00:05.00,0:00:08.00,Caption,,0,0,0,,السطر الثالث
"""


class ReelSubtitleSeparationTests(unittest.TestCase):
    def test_horizontal_master_keeps_bottom_caption_style(self):
        style = next(line for line in generate_voice.build_ass_header().splitlines() if line.startswith("Style: Caption,"))
        self.assertIn(",2,70,70,90,1", style)

    def test_reel_ass_uses_vertical_top_safe_style_and_clipped_times(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "narration.ass"
            output = Path(directory) / "reel.ass"
            source.write_text(ASS_SOURCE, encoding="utf-8")
            original = source.read_text(encoding="utf-8")
            write_reel_subtitles(source, 1.0, 6.0, output)
            rendered = output.read_text(encoding="utf-8")
            self.assertEqual(source.read_text(encoding="utf-8"), original)

        self.assertIn("PlayResX: 1080", rendered)
        self.assertIn("PlayResY: 1920", rendered)
        style = next(line for line in rendered.splitlines() if line.startswith("Style: Caption,"))
        self.assertIn(",8,124,124,260,1", style)
        events = [line for line in rendered.splitlines() if line.startswith("Dialogue:")]
        self.assertEqual(len(events), 3)
        parsed = [line.split(":", 1)[1].lstrip().split(",", 9) for line in events]
        self.assertEqual([(row[1], row[2]) for row in parsed], [
            ("0:00:00.00", "0:00:01.00"),
            ("0:00:01.00", "0:00:04.00"),
            ("0:00:04.00", "0:00:05.00"),
        ])

    def test_reel_cta_uses_a_separate_safe_lane(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cta.ass"
            assemble_video.write_cta_ass(path, 0.0, 4.0, "رسالة")
            style = next(line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("Style: CTA,"))
        self.assertIn(",8,70,70,620,1", style)

    def test_reel_uses_clean_video_and_full_master_audio(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "narration.ass"
            clean_video = root / "clean.mp4"
            full_master = root / "full.mp4"
            output = root / "short.mp4"
            source.write_text(ASS_SOURCE, encoding="utf-8")
            with patch.object(assemble_video, "CLIPS_DIR", root), patch.object(assemble_video, "run") as run_mock, patch.object(assemble_video, "probe_duration", return_value=3.0):
                duration = assemble_video.create_short(
                    clean_video, full_master, source,
                    {"start_seconds": 1.0, "end_seconds": 4.0},
                    1, "youtube", output,
                )

        command = run_mock.call_args.args[0]
        input_positions = [index for index, value in enumerate(command[:-1]) if value == "-i"]
        self.assertEqual(command[input_positions[0] + 1], str(clean_video))
        self.assertEqual(command[input_positions[1] + 1], str(full_master))
        self.assertEqual([command[index + 1] for index, value in enumerate(command[:-1]) if value == "-map"], ["0:v:0", "1:a:0?"])
        self.assertIn("reel_short_1_youtube.ass", command[command.index("-vf") + 1])
        self.assertNotIn(str(source), command)
        self.assertEqual(duration, 3.0)


if __name__ == "__main__":
    unittest.main()

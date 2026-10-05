import unittest
from unittest.mock import patch

from scripts.audio_matching import build_audio_record, choose_decision


class AudioMatchingTests(unittest.TestCase):
    def test_clip_with_audio_defaults_to_ducking(self):
        decision, _ = choose_decision({"present": True})
        self.assertEqual(decision, "ORIGINAL AUDIO + VOICE DUCKING")

    def test_clip_without_audio_uses_voice_only(self):
        decision, _ = choose_decision({"present": False})
        self.assertEqual(decision, "VOICE ONLY")

    def test_invalid_override_is_rejected(self):
        with self.assertRaises(ValueError):
            choose_decision({"present": True}, "invented effect")

    @patch("scripts.audio_matching.probe_audio", return_value={"present": True, "codec": "aac", "channels": 2, "sample_rate": "48000", "duration": 3.0})
    def test_manifest_record_is_not_historical_evidence(self, _probe):
        record = build_audio_record("clip.mp4")
        self.assertFalse(record["historical_claim"])
        self.assertIn("decision", record)
        self.assertEqual(record["analysis"]["codec"], "aac")


if __name__ == "__main__":
    unittest.main()

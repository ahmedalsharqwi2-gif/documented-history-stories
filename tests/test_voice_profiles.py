import json
import tempfile
import unittest
from pathlib import Path

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from voice_profiles import resolve_reference_profile  # noqa: E402


class VoiceProfileResolverTests(unittest.TestCase):
    def test_resolves_all_bundled_profiles_and_exact_transcripts(self):
        catalog_path = ROOT / "assets/voices/voice_profiles.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.assertEqual(len(catalog["profiles"]), 9)
        self.assertIn("octopus_narrator", catalog["profiles"])
        for key in catalog["profiles"]:
            with self.subTest(profile=key):
                selected, label, wav, transcript = resolve_reference_profile(key, catalog_path, ROOT)
                self.assertEqual(selected, key)
                self.assertTrue(label)
                self.assertTrue(wav.is_file())
                self.assertGreater(wav.stat().st_size, 1000)
                self.assertTrue(transcript)

    def test_unknown_profile_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown voice profile"):
            resolve_reference_profile("not-a-profile", ROOT / "assets/voices/voice_profiles.json", ROOT)

    def test_manifest_default_is_used_when_selection_is_empty(self):
        catalog = json.loads((ROOT / "assets/voices/voice_profiles.json").read_text(encoding="utf-8"))
        selected, _, _, _ = resolve_reference_profile("", ROOT / "assets/voices/voice_profiles.json", ROOT)
        self.assertEqual(selected, catalog["default"])

    def test_production_uses_fixed_octopus_voice_while_audio_test_can_select_profiles(self):
        catalog = json.loads((ROOT / "assets/voices/voice_profiles.json").read_text(encoding="utf-8"))
        production = (ROOT / ".github/workflows/main.yml").read_text(encoding="utf-8")
        self.assertIn("- octopus_narrator", production)
        self.assertNotIn("- mohamed_elbed", production)
        test_audio = (ROOT / ".github/workflows/test-story-audio.yml").read_text(encoding="utf-8")
        for key in catalog["profiles"]:
            with self.subTest(profile=key):
                self.assertIn(f"- {key}", test_audio)


if __name__ == "__main__":
    unittest.main()

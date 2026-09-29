import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import generate_script  # noqa: E402
from llm_gateway import OutputError  # noqa: E402


def sample_episode(word_count=310):
    narration = " ".join(["الحملة" for _ in range(word_count)]) + "."
    return {
        "title": "قرار غيّر مسار المعركة",
        "hook": "كيف غيّر قرار واحد مسار المعركة؟",
        "region": "العصر العباسي",
        "source_type": "كتاب تاريخي",
        "source_reference": "الطبري، تاريخ الرسل والملوك",
        "narration": narration,
        "visual_keywords": [
            "historic map", "ancient fortress", "archival manuscript", "desert landscape",
            "stone ruins", "old battlefield", "historic documents", "museum artifact",
        ],
        "caption": "واقعة تاريخية موثقة تكشف أثر القرار الحاسم.",
        "phonetic_hints": [
            {"word": "الحملة", "phonetic": "الْحَمْلَة"},
        ],
    }


class IslamicGeneratorTests(unittest.TestCase):
    def test_schema_contains_the_complete_json_output_in_stable_order(self):
        self.assertEqual(list(generate_script.EPISODE_SCHEMA["properties"]), list(generate_script.REQUIRED_KEYS))
        self.assertEqual(generate_script.EPISODE_SCHEMA["required"], list(generate_script.REQUIRED_KEYS))
        gemini_schema = generate_script.to_gemini_schema(generate_script.EPISODE_SCHEMA)
        self.assertNotIn("additionalProperties", gemini_schema)

    def test_normalizer_keeps_only_valid_phonetic_hints_and_drops_extra_fields(self):
        raw = sample_episode()
        raw["phonetic_hints"] += [
            "bad item",
            {"word": "الحملة", "phonetic": "الحمله"},
            {"word": "كلمة غائبة", "phonetic": "كَلِمَة غائِبَة"},
        ]
        raw["unexpected"] = "provider-added field"
        normalized = generate_script.normalize_episode(raw)
        self.assertEqual(normalized["phonetic_hints"], [{"word": "الحملة", "phonetic": "الْحَمْلَة"}])
        self.assertNotIn("unexpected", normalized)
        generate_script.validate_episode(normalized)

    def test_missing_optional_hints_and_keywords_get_safe_fallbacks(self):
        raw = sample_episode()
        raw.pop("phonetic_hints")
        raw["visual_keywords"] = None
        normalized = generate_script.normalize_episode(raw)
        self.assertEqual(normalized["phonetic_hints"], [])
        self.assertEqual(normalized["visual_keywords"], generate_script.DEFAULT_VISUAL_KEYWORDS)

    def test_rejects_oversized_metadata_instead_of_silently_truncating(self):
        raw = sample_episode()
        raw["title"] = "x" * 101
        with self.assertRaisesRegex(OutputError, "title.*أطول"):
            generate_script.normalize_episode(raw)

    def test_rejects_wrong_core_field_types(self):
        raw = sample_episode()
        raw["source_reference"] = ["not", "a", "string"]
        with self.assertRaisesRegex(OutputError, "source_reference.*نصًا"):
            generate_script.normalize_episode(raw)

    def test_rejects_overlong_narration_by_word_limit(self):
        raw = sample_episode(generate_script.MAX_NARRATION_WORDS + 1)
        normalized = generate_script.normalize_episode(raw)
        with self.assertRaisesRegex(OutputError, "narration طويلة"):
            generate_script.validate_episode(normalized)

    def test_rejects_truncated_narration_and_bad_source_fields(self):
        raw = sample_episode()
        raw["narration"] = raw["narration"].rstrip(".")
        normalized = generate_script.normalize_episode(raw)
        with self.assertRaisesRegex(OutputError, "مقطوع"):
            generate_script.validate_episode(normalized)
        raw = sample_episode()
        raw["source_reference"] = "  "
        with self.assertRaisesRegex(OutputError, "source_reference فارغ"):
            generate_script.validate_episode(generate_script.normalize_episode(raw))

    def test_json_output_order_matches_downstream_contract(self):
        normalized = generate_script.normalize_episode(sample_episode())
        self.assertEqual(list(normalized), list(generate_script.REQUIRED_KEYS))


if __name__ == "__main__":
    unittest.main()

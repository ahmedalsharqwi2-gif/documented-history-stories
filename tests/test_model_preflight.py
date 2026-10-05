import json
import os
import unittest
from unittest.mock import patch
from pathlib import Path


class ModelPolicyTests(unittest.TestCase):
    def test_policy_has_one_shared_schema_and_provider_order(self):
        policy = json.loads(Path("config/model_policy.json").read_text(encoding="utf-8"))
        self.assertEqual(policy["schema_version"], 1)
        self.assertEqual(list(policy["providers"]), ["gemini", "fallback", "openrouter"])
        for provider in policy["providers"].values():
            self.assertTrue(provider["preferred_models"])
            self.assertIn(503, provider["retry_statuses"])


    def test_select_never_returns_unlisted_or_stale_default(self):
        from scripts.model_preflight import select
        self.assertEqual(select(["old-model"], [], [], "old-model"), ("", []))
        self.assertEqual(select(["old-model"], [], ["new-model"], "old-model"), ("new-model", []))

    def test_forbidden_catalog_does_not_validate_configured_model(self):
        from scripts.model_preflight import discover_openai_provider
        with patch.dict(os.environ, {"LLM_FALLBACK_MODEL": "stale-model"}, clear=True), \
             patch("scripts.model_preflight.request_json", return_value=(403, {})):
            self.assertEqual(discover_openai_provider(
                "Fallback LLM", "https://example.test/chat/completions", "test",
                ["stale-model"], ("LLM_FALLBACK_MODEL",), "stale-model"
            ), ("", []))

    def test_preflight_is_importable_without_third_party_dependencies(self):
        import scripts.model_preflight as preflight
        self.assertEqual(preflight.DEFAULT_GEMINI, "gemini-2.5-flash")


if __name__ == "__main__":
    unittest.main()

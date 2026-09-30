import unittest
from unittest.mock import patch

from scripts import generate_script as gs


class IslamicFallbackTests(unittest.TestCase):
    def test_openrouter_reports_groq_as_next_provider(self):
        with (
            patch.object(gs, "ACTIVE_PROVIDER", "openrouter"),
            patch.object(gs, "FALLBACK_API_KEY", "groq-test"),
        ):
            self.assertTrue(gs.has_next_model())

    def test_switches_from_openrouter_to_configured_fallback(self):
        with (
            patch.object(gs, "ACTIVE_PROVIDER", "openrouter"),
            patch.object(gs, "FALLBACK_API_KEY", "groq-test"),
            patch.object(gs, "FALLBACK_MODEL", "llama-test"),
        ):
            self.assertTrue(gs.switch_to_next_model())
            self.assertEqual(gs.ACTIVE_PROVIDER, "fallback")
            self.assertEqual(gs.ACTIVE_MODEL, "llama-test")

    def test_compatible_client_maps_openai_response(self):
        response = type(
            "Response",
            (),
            {
                "status_code": 200,
                "text": "",
                "json": lambda self: {
                    "choices": [{"message": {"content": "نص احتياطي"}}],
                    "usage": {},
                },
            },
        )()
        content = gs.make_content("user", "اختبار")
        config = type(
            "Config",
            (),
            {"system_instruction": "نظام", "temperature": 0.2, "max_output_tokens": 20},
        )()
        client = gs.CompatibleChatModels(
            "test-key", "https://example.invalid/v1/chat/completions", ["model"], "Test"
        )
        with patch.object(gs.requests, "post", return_value=response) as post:
            result = client.generate_content(model="model", contents=[content], config=config)
        self.assertEqual(result.text, "نص احتياطي")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["messages"][-1]["content"], "اختبار")
        self.assertNotIn("reasoning", payload)
        self.assertLessEqual(payload["max_tokens"], gs.FALLBACK_MAX_TOKENS)


if __name__ == "__main__":
    unittest.main()

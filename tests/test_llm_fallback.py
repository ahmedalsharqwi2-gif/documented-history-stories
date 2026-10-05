import unittest
from unittest.mock import patch

from scripts import generate_script as gs


class DocumentedHistoryFallbackTests(unittest.TestCase):
    def test_internal_narration_headings_are_removed_before_validation(self):
        text = "تمهيد موثق يبدأ بالحدث مباشرة.\nالنتيجة\nثم تكشفت الحقيقة في نهاية القصة."
        cleaned = gs.strip_internal_narration_labels(text)
        self.assertNotIn("النتيجة", cleaned)
        self.assertIn("ثم تكشفت الحقيقة", cleaned)

    def test_prefixed_internal_narration_heading_keeps_spoken_text(self):
        cleaned = gs.strip_internal_narration_labels("الخاتمة: انتهت الحادثة بعد ظهور الدليل.")
        self.assertEqual(cleaned, "انتهت الحادثة بعد ظهور الدليل.")

    def test_embedded_internal_label_is_removed(self):
        cleaned = gs.strip_internal_narration_labels("ثم كانت النتيجة واضحة بعد ظهور الدليل.")
        self.assertNotIn("النتيجة", cleaned)
        self.assertIn("كانت واضحة", cleaned)

    def test_legacy_labeled_reply_derives_hook_from_first_narration_sentence(self):
        reply = (
            "TITLE: سقوط مدينة تاريخية\n"
            "CAPTION: قصة تاريخية موثقة\n"
            "REGION: الأندلس في أواخر القرن الخامس الهجري\n"
            "SOURCE_TYPE: موسوعة تاريخية\n"
            "SOURCE_REFERENCE: مرجع تاريخي موثوق\n"
            "NARRATION:\n"
            "كيف انتهت مدينة عظيمة في ليلة واحدة بعد حصار طويل؟ ثم تتابعت الأحداث حتى أُغلقت أبوابها."
        )
        episode = gs.parse_story_reply(reply, "اختبار", "القصة")
        self.assertEqual(episode["hook"], "كيف انتهت مدينة عظيمة في ليلة واحدة بعد حصار طويل؟")
        self.assertEqual(episode["region"], "الأندلس في أواخر القرن الخامس الهجري")

    def test_model_hook_is_replaced_when_it_does_not_match_narration(self):
        reply = (
            "TITLE: حصار تاريخي\nCAPTION: قصة موثقة\nREGION: الشام\n"
            "SOURCE_TYPE: كتاب تاريخي\nSOURCE_REFERENCE: مرجع موثق\n"
            "HOOK: لماذا انتصر الجيش؟\n"
            "NARRATION: كيف صمدت قلعة صغيرة أمام جيش عظيم طوال أشهر عديدة في الشتاء؟ ثم تبدلت موازين القوة."
        )
        episode = gs.parse_story_reply(reply, "اختبار", "القصة")
        self.assertEqual(episode["hook"], "كيف صمدت قلعة صغيرة أمام جيش عظيم طوال أشهر عديدة في الشتاء؟")
        self.assertEqual(gs.validate_hook(episode["hook"], episode["narration"]), [])

    def test_overlong_first_sentence_is_split_into_a_valid_hook(self):
        narration = "هذه بداية طويلة جدًا للقصة حتى تتجاوز الحد المطلوب للهوك وتستمر في وصف المكان والحدث بالتفصيل قبل أن تبدأ بقية القصة. ثم تتوالى الأحداث."
        normalized, hook = gs._split_overlong_first_sentence(narration)
        self.assertEqual(len(hook.split()), 16)
        self.assertEqual(gs.validate_hook(hook, normalized), [])

    def test_openrouter_reports_groq_as_next_provider(self):
        with (
            patch.object(gs, "ACTIVE_PROVIDER", "openrouter"),
            patch.object(gs, "FALLBACK_API_KEY", "groq-test"),
            patch.object(gs, "FALLBACK_MODEL", "llama-test"),
        ):
            self.assertTrue(gs.has_next_model())

    def test_switches_from_openrouter_to_configured_fallback(self):
        with (
            patch.object(gs, "ACTIVE_PROVIDER", "openrouter"),
            patch.object(gs, "VISITED_PROVIDERS", {"gemini", "openrouter"}),
            patch.object(gs, "FALLBACK_API_KEY", "groq-test"),
            patch.object(gs, "FALLBACK_MODEL", "llama-test"),
        ):
            self.assertTrue(gs.switch_to_next_model())
            self.assertEqual(gs.ACTIVE_PROVIDER, "fallback")
            self.assertEqual(gs.ACTIVE_MODEL, "llama-test")

    def test_switches_from_fallback_to_openrouter(self):
        with (
            patch.object(gs, "ACTIVE_PROVIDER", "fallback"),
            patch.object(gs, "VISITED_PROVIDERS", {"gemini", "fallback"}),
            patch.object(gs, "OPENROUTER_API_KEY", "router-test"),
            patch.object(gs, "OPENROUTER_MODEL", "router-model"),
        ):
            self.assertTrue(gs.switch_to_next_model())
            self.assertEqual(gs.ACTIVE_PROVIDER, "openrouter")
            self.assertEqual(gs.ACTIVE_MODEL, "router-model")

    def test_model_unavailable_400_invalid_argument_is_classified(self):
        self.assertTrue(gs._is_model_unavailable(Exception("400 INVALID_ARGUMENT")))

    def test_compatible_client_preserves_quota_error_after_all_models_fail(self):
        response = type("Response", (), {"status_code": 429, "text": "rate limit"})()
        client = gs.CompatibleChatModels(
            "test-key", "https://example.invalid/v1/chat/completions", ["model"], "Fallback LLM"
        )
        with patch.object(gs.requests, "post", return_value=response):
            with self.assertRaises(gs.QuotaExhausted):
                client.generate_content(model="model", contents=[], config=object())

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

    def test_openrouter_has_independent_token_cap(self):
        client = gs.CompatibleChatModels(
            "test-key", "https://example.invalid/v1/chat/completions", ["model"], "OpenRouter"
        )
        content = gs.make_content("user", "اختبار")
        config = type("Config", (), {"system_instruction": "نظام", "temperature": 0.2, "max_output_tokens": 8000})()
        response = type(
            "Response",
            (),
            {"status_code": 200, "text": "", "json": lambda self: {"choices": [{"message": {"content": "نص"}}], "usage": {}}},
        )()
        with patch.object(gs.requests, "post", return_value=response) as post:
            client.generate_content(model="model", contents=[content], config=config)
        self.assertLessEqual(post.call_args.kwargs["json"]["max_tokens"], gs.OPENROUTER_MAX_TOKENS)

    def test_long_context_reserves_room_under_provider_tpm_limit(self):
        client = gs.CompatibleChatModels(
            "test-key", "https://example.invalid/v1/chat/completions", ["model"], "Fallback LLM"
        )
        content = gs.make_content("user", "سياق طويل " * 7000)
        config = type(
            "Config",
            (),
            {"system_instruction": "نظام", "temperature": 0.2, "max_output_tokens": 1800},
        )()
        response = type(
            "Response",
            (),
            {
                "status_code": 200,
                "text": "",
                "json": lambda self: {"choices": [{"message": {"content": "نص"}}], "usage": {}},
            },
        )()
        with patch.object(gs.requests, "post", return_value=response) as post:
            client.generate_content(model="model", contents=[content], config=config)
        self.assertLess(post.call_args.kwargs["json"]["max_tokens"], 1800)


if __name__ == "__main__":
    unittest.main()

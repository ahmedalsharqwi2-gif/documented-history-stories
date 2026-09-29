import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import llm_gateway  # noqa: E402
from llm_gateway import (  # noqa: E402
    ModelCallLimitExceeded,
    OutputError,
    Provider,
    classify_error,
    generate_valid_episode,
    parse_episode_json,
    record_model_call,
    reset_model_call_count,
)


class LlmGatewayTests(unittest.TestCase):
    def setUp(self):
        reset_model_call_count()

    def tearDown(self):
        reset_model_call_count()

    def test_parses_json_with_preamble_fence_and_think_block(self):
        raw = 'تم التحليل\n<think>hidden</think>\n```json\n{"title":"x","nested":{"v":1}}\n```'
        self.assertEqual(parse_episode_json(raw), {"title": "x", "nested": {"v": 1}})

    def test_rejects_truncated_json_and_non_object(self):
        with self.assertRaises(OutputError) as ctx:
            parse_episode_json('{"title":"unfinished"')
        self.assertTrue(ctx.exception.truncated)
        with self.assertRaisesRegex(OutputError, "كائن JSON"):
            parse_episode_json('[1, 2]')

    def test_classifies_daily_quota_and_invalid_argument_as_non_retryable_provider_errors(self):
        self.assertEqual(classify_error(RuntimeError("429 free-models-per-day quota exceeded")), "quota")
        self.assertEqual(classify_error(RuntimeError("400 INVALID_ARGUMENT")), "permanent")
        self.assertEqual(classify_error(RuntimeError("503 UNAVAILABLE")), "transient")

    def test_global_request_cap_is_enforced_before_sending(self):
        llm_gateway.MODEL_CALL_COUNT = llm_gateway.LLM_MAX_CALLS
        with self.assertRaises(ModelCallLimitExceeded):
            record_model_call("test-provider")
        self.assertEqual(llm_gateway.MODEL_CALL_COUNT, llm_gateway.LLM_MAX_CALLS)

    def test_provider_retries_and_fallbacks_never_exceed_the_global_cap(self):
        def unavailable(system, user, budget):
            record_model_call("unavailable-provider")
            raise RuntimeError("503 UNAVAILABLE")

        providers = [Provider(f"provider-{index}", unavailable) for index in range(10)]
        with self.assertRaises(ModelCallLimitExceeded):
            generate_valid_episode(
                "system", "user", 1000, providers,
                validate=lambda episode: None, sleep=lambda seconds: None,
            )
        self.assertEqual(llm_gateway.MODEL_CALL_COUNT, llm_gateway.LLM_MAX_CALLS)

    def test_permanent_provider_error_falls_through_to_next_provider(self):
        good = {"title": "x"}

        def bad_provider(system, user, budget):
            record_model_call("provider-a")
            raise RuntimeError("HTTP 400 INVALID_ARGUMENT")

        def good_provider(system, user, budget):
            record_model_call("provider-b")
            return json.dumps(good)

        result, name = generate_valid_episode(
            "system", "user", 1000,
            [Provider("a", bad_provider), Provider("b", good_provider)],
            validate=lambda episode: None,
        )
        self.assertEqual(result, good)
        self.assertEqual(name, "b")
        self.assertEqual(llm_gateway.MODEL_CALL_COUNT, 2)

    def test_invalid_output_is_retried_once_with_feedback_within_budget(self):
        received_messages = []

        def provider(system, user, budget):
            record_model_call("retry-provider")
            received_messages.append(user)
            if len(received_messages) == 1:
                return "not JSON"
            return '{"title":"valid"}'

        result, _ = generate_valid_episode(
            "system", "user", 1000, [Provider("retry", provider)],
            validate=lambda episode: None,
        )
        self.assertEqual(result, {"title": "valid"})
        self.assertEqual(len(received_messages), 2)
        self.assertIn("تصحيح مطلوب", received_messages[1])


if __name__ == "__main__":
    unittest.main()

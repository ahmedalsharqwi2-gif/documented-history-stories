import os
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import generate_script as generator


class GenerationRecoveryTests(unittest.TestCase):
    def test_short_minute_quota_can_recover_but_daily_quota_cannot(self):
        self.assertAlmostEqual(generator._minute_quota_wait(RuntimeError(
            '429 RESOURCE_EXHAUSTED PerMinute Please retry in 18.74s.')), 19.74)
        self.assertIsNone(generator._minute_quota_wait(RuntimeError(
            '429 RESOURCE_EXHAUSTED PerDay Please retry in 18s.')))
        self.assertIsNone(generator._minute_quota_wait(RuntimeError(
            '429 RESOURCE_EXHAUSTED PerMinute Please retry in 120s.')))

    def test_incomplete_historical_report_cannot_reach_proofreading(self):
        story = {"hook": "اختبار", "region": "مكان", "source_type": "أرشيف",
                 "source_reference": "أرشيف", "narration": "نص.",
                 "historical_verification_report": {"decision": "APPROVED"}}
        with patch.object(generator, 'call_model', return_value=('reply', 'STOP')) as call, \
             patch.object(generator, 'parse_story_reply', return_value=story), \
             patch.object(generator, 'proofread_narration_for_tts') as proofread:
            with self.assertRaises(generator.AttemptFailed):
                generator.run_single_attempt(None, 'system', [], [], [], 650, 'test')
        self.assertEqual(call.call_count, 3)
        self.assertIn('تقرير التحقق ناقص', call.call_args.args[2])
        proofread.assert_not_called()

    def test_prompt_names_all_historical_report_fields(self):
        from scripts.historical_verification_gate import REQUIRED_REPORT_FIELDS, REQUIRED_PRE_FIELDS
        prompt = generator.build_story_prompt([], [], [], 650)
        for field in REQUIRED_REPORT_FIELDS | REQUIRED_PRE_FIELDS:
            self.assertIn(field, prompt)

    def setUp(self):
        original = generator.VISITED_PROVIDERS.copy()
        self.addCleanup(lambda: (generator.VISITED_PROVIDERS.clear(), generator.VISITED_PROVIDERS.update(original)))

    def test_production_keeps_the_primary_secret(self):
        import yaml
        workflow = yaml.safe_load(Path('.github/workflows/main.yml').read_text())
        steps = workflow['jobs']['build-and-publish']['steps']
        generation = next(s for s in steps if s['name'] == 'Generate complete documented history story script')
        self.assertEqual(generation['env']['GEMINI_API_KEY'], '${{ secrets.GEMINI_API_KEY }}')

    def test_empty_gemini_response_switches_instead_of_reparsing(self):
        from types import SimpleNamespace
        response = SimpleNamespace(text="", candidates=[SimpleNamespace(finish_reason="STOP")], usage_metadata=None)
        client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs: response))
        with self.assertRaises(generator.ModelUnavailable):
            generator.call_model(client, [], "test", generator.free_text_config, "system", 100, "test")

    def test_fallback_start_does_not_revisit_failed_provider(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY': '', 'TOPIC_BANK_REQUIRED': 'false'}), \
             patch.multiple(generator, FALLBACK_API_KEY='test', FALLBACK_MODEL='fallback-model',
                            OPENROUTER_API_KEY='test', OPENROUTER_MODEL='router-model',
                            MODEL_CANDIDATES=[], MAX_ATTEMPTS=1), \
             patch.object(generator, 'ProviderClient'), \
             patch.object(generator, 'load_system_prompt', return_value='test'), \
             patch.object(generator, 'load_used_history', return_value=[]), \
             patch.object(generator, 'load_used_regions', return_value=[]), \
             patch.object(generator, 'load_used_hooks', return_value=[]), \
             patch.object(generator, 'TopicHistory') as history, \
             patch.object(generator, 'find_duplicate', return_value=None), \
             patch.object(generator, 'run_single_attempt') as run:
            history.return_value.entries = []
            seen = []
            def fail(*args):
                seen.append(generator.ACTIVE_PROVIDER)
                raise generator.ModelUnavailable('provider unavailable')
            run.side_effect = fail
            with self.assertRaises(SystemExit):
                generator.generate_episode()
            self.assertEqual(seen, ['fallback', 'openrouter'])
            self.assertFalse(generator.has_next_model())

    def test_provider_switch_preserves_generation_retry(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY': '', 'TOPIC_BANK_REQUIRED': 'false'}), \
             patch.multiple(generator, FALLBACK_API_KEY='test', FALLBACK_MODEL='fallback-model',
                            OPENROUTER_API_KEY='test', OPENROUTER_MODEL='router-model',
                            MODEL_CANDIDATES=[], MAX_ATTEMPTS=2), \
             patch.object(generator, 'ProviderClient'), \
             patch.object(generator, 'load_system_prompt', return_value='test'), \
             patch.object(generator, 'load_used_history', return_value=[]), \
             patch.object(generator, 'load_used_regions', return_value=[]), \
             patch.object(generator, 'load_used_hooks', return_value=[]), \
             patch.object(generator, 'TopicHistory') as history, \
             patch.object(generator, 'find_duplicate', return_value=None), \
             patch.object(generator, 'run_single_attempt', side_effect=[
                 generator.ModelUnavailable('unavailable'), generator.AttemptFailed('invalid output'), {'title': 'valid'}
             ]) as run:
            history.return_value.entries = []
            self.assertEqual(generator.generate_episode(), {'title': 'valid'})
            self.assertEqual(run.call_count, 3)

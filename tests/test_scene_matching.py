import unittest
from unittest.mock import patch
from scripts.assemble_video import build_scene_plan
from scripts.fetch_clips import search_with_fallback


class SceneMatchingTests(unittest.TestCase):
    def test_missing_keyword_cannot_take_an_unrelated_clip(self):
        with self.assertRaisesRegex(RuntimeError, 'No matching clip'):
            build_scene_plan([{'file': 'cross.mp4', 'keyword': 'church'}],
                             {'narration': 'وصف المدينة.', 'visual_keywords': ['castle']}, None, 2)

    @patch('scripts.fetch_clips.search_pexels', return_value=[])
    def test_empty_search_does_not_try_generic_historical_backgrounds(self, search):
        self.assertEqual(search_with_fallback('castle', 'key', set(), 2), [])
        search.assert_called_once_with('castle', 'key', set(), 2)

    def test_reuse_stays_with_matching_keyword_and_audio_decision(self):
        plan = build_scene_plan([{'file': 'castle.mp4', 'keyword': 'castle', 'audio': {'decision': 'MUTE'}}],
                                {'narration': 'وصف المدينة. وصف الحصار.', 'visual_keywords': ['castle']}, None, 4)
        self.assertTrue(all(s['file'] == 'castle.mp4' and s['audio_decision'] == 'MUTE' for s in plan))

import tempfile
import unittest
from pathlib import Path

from scripts.topic_history import (
    DuplicateTopicError,
    TopicHistory,
    TopicHistoryError,
    find_duplicate,
    load_history,
    normalize_text,
)


class TopicHistoryTests(unittest.TestCase):
    def test_arabic_diacritics_and_alef_variants_normalize(self):
        self.assertEqual(
            normalize_text("إِشَارَةُ أُورِيُونَ الغامضة"),
            normalize_text("اشاره اوريون الغامضه"),
        )

    def test_same_incident_with_reworded_title_is_detected(self):
        previous = [{
            "title": "لغز اختفاء سفينة ماري سيليست في المحيط الأطلسي",
            "hook": "حادثة اختفاء السفينة ماري سيليست بالمحيط الأطلسي",
        }]
        proposed = {
            "title": "حقيقة اختفاء سفينة ماري سيليست في المحيط الأطلسي",
            "hook": "حادثة اختفاء السفينة ماري سيليست بالمحيط الأطلسي",
        }
        self.assertIsNotNone(find_duplicate(proposed, previous))

    def test_unrelated_subject_is_not_blocked(self):
        previous = [{"title": "لغز اختفاء سفينة ماري سيليست في المحيط الأطلسي"}]
        proposed = {"title": "كيف يخزن الدماغ الذكريات أثناء النوم"}
        self.assertIsNone(find_duplicate(proposed, previous))

    def test_reservation_is_permanent_and_duplicate_reservation_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "topic_history.json"
            registry = TopicHistory(path)
            candidate = {
                "title": "كيف تتشكل الشفق القطبي فوق القطبين",
                "hook": "تصادم الجسيمات الشمسية مع الغلاف المغناطيسي للأرض",
            }
            reserved = registry.reserve(candidate)
            reloaded = TopicHistory(path)
            self.assertEqual(len(reloaded.entries), 1)
            self.assertEqual(reloaded.entries[0]["id"], reserved["id"])
            with self.assertRaises(DuplicateTopicError):
                reloaded.reserve(candidate)
            reloaded.mark_published(candidate)
            self.assertEqual(TopicHistory(path).entries[0]["status"], "published")

    def test_invalid_history_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "topic_history.json"
            path.write_text("not valid json", encoding="utf-8")
            with self.assertRaises(TopicHistoryError):
                load_history(path)


if __name__ == "__main__":
    unittest.main()


class ReminderTopicGenerationIntegrationTests(unittest.TestCase):
    def test_permanent_topic_history_is_added_to_generator_context(self):
        from unittest.mock import patch
        from scripts import generate_script as gs

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "topic_history.json"
            TopicHistory(path).reserve({
                "title": "رسالة خالد بن الوليد قبل معركة مؤتة",
                "hook": "اختيار قائد يحمل خبرًا حاسمًا إلى ساحة المعركة",
            })
            with patch.object(gs, "TOPIC_HISTORY_PATH", path), patch.object(
                gs, "_load_history_field", return_value=[]
            ):
                self.assertIn("رسالة خالد بن الوليد قبل معركة مؤتة", gs.load_used_history())
                self.assertIn("اختيار قائد يحمل خبرًا حاسمًا", gs.load_used_hooks()[0])

    def test_history_in_story_prompt_is_json_data_not_instructions(self):
        from scripts import generate_script as gs

        prompt = gs.build_story_prompt(["عنوان سابق"], [], ["واقعة سابقة"], 600)
        self.assertIn("بيانات غير موثوقة", prompt)
        self.assertIn('["عنوان سابق"]', prompt)
        self.assertIn('["واقعة سابقة"]', prompt)

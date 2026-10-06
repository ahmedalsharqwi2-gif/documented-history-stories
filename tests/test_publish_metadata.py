import unittest

from scripts.publish_buffer import HISTORICAL_SOURCE, build_post_text, ensure_caption_hashtags


class PublishMetadataTests(unittest.TestCase):
    def test_empty_caption_gets_history_defaults(self):
        text = ensure_caption_hashtags("رحلة تاريخية", "")
        self.assertIn("رحلة تاريخية", text)
        self.assertIn("#تاريخ", text)
        self.assertIn("#قصص_تاريخية", text)

    def test_full_video_removes_shorts_but_keeps_relevant_tags(self):
        text = build_post_text("youtube", "full_video", "عنوان", "#Shorts")
        self.assertNotIn("#Shorts", text)
        self.assertIn("#تاريخ", text)
        self.assertNotIn(HISTORICAL_SOURCE, text)

    def test_explicit_source_is_preserved_in_full_description(self):
        source = "مرجع الحلقة: وثيقة تاريخية"
        text = build_post_text(
            "youtube", "full_video", "عنوان", "#تاريخ",
            source_reference=source,
        )
        self.assertIn(source, text)
        self.assertNotIn(HISTORICAL_SOURCE, text)

    def test_source_is_not_added_to_short_description(self):
        text = build_post_text("facebook", "short", "عنوان", "مقتطف")
        self.assertNotIn(HISTORICAL_SOURCE, text)


if __name__ == "__main__":
    unittest.main()

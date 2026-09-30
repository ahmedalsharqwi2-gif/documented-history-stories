import unittest

from scripts.publish_buffer import build_post_text, ensure_caption_hashtags


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


if __name__ == "__main__":
    unittest.main()

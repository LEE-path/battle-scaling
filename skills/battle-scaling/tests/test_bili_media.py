"""Bilibili URL/page selection is pure; no credentials or network are needed."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import bili_media


class BilibiliPageSelectionTests(unittest.TestCase):
    bv = 'BV1xx411c7mD'

    def test_link_page_is_preserved_without_override(self):
        self.assertEqual(bili_media.canonical(f'https://www.bilibili.com/video/{self.bv}?p=5'),
                         f'https://www.bilibili.com/video/{self.bv}?p=5')

    def test_explicit_page_has_priority(self):
        self.assertEqual(bili_media.canonical(f'https://www.bilibili.com/video/{self.bv}?p=5', 3),
                         f'https://www.bilibili.com/video/{self.bv}?p=3')
        self.assertEqual(bili_media.canonical('https://www.bilibili.com/video/av123?p=5', 3),
                         'https://www.bilibili.com/video/av123?p=3')

    def test_bare_identifiers_default_to_first_page(self):
        self.assertEqual(bili_media.canonical(self.bv), f'https://www.bilibili.com/video/{self.bv}?p=1')
        self.assertEqual(bili_media.canonical('av123'), 'https://www.bilibili.com/video/av123?p=1')

    def test_short_url_preserves_resolved_page(self):
        fake = SimpleNamespace(get=lambda *a, **k: SimpleNamespace(url=f'https://www.bilibili.com/video/{self.bv}?p=7'))
        with patch.object(bili_media, 'session', return_value=fake):
            self.assertEqual(bili_media.canonical('https://b23.tv/a'), f'https://www.bilibili.com/video/{self.bv}?p=7')
            self.assertEqual(bili_media.canonical('https://b23.tv/a', 2), f'https://www.bilibili.com/video/{self.bv}?p=2')

    def test_invalid_pages_are_rejected(self):
        for page in (0, -1, True, 1.5, 'not-a-page'):
            with self.subTest(page=page), self.assertRaises(ValueError):
                bili_media.canonical(self.bv, page)
        for value in ('0', '-2', 'nan'):
            with self.subTest(url_page=value), self.assertRaises(ValueError):
                bili_media.canonical(f'https://www.bilibili.com/video/{self.bv}?p={value}')

    def test_bv_text_in_an_unrelated_url_is_not_a_video_identifier(self):
        with self.assertRaises(ValueError):
            bili_media.canonical(f'https://example.invalid/{self.bv}?p=3')


if __name__ == '__main__':
    unittest.main()

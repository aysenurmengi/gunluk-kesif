"""Ortak model, tarih dönüşümü ve tekrar ayıklamanın davranış testleri."""

from dataclasses import replace
from datetime import datetime, timezone
import unittest

from backend.app.models import Source
from backend.app.services.content import normalize_article, parse_publication_date, remove_duplicates


SOURCE = Source("sample", "Örnek Kaynak", "https://example.com/rss", "ekonomi")


def make_item(url="https://example.com/haber", title="Başlık"):
    return normalize_article({"title": title, "link": url, "published_at": ""}, SOURCE)


class ContentTests(unittest.TestCase):
    def test_model_keeps_source_metadata_and_standardizes_fields(self):
        item = normalize_article({"title": "  Başlık  ", "link": " https://example.com/haber ", "published_at": "Tue, 29 Sep 2026 20:02:00 +0300"}, SOURCE)
        self.assertEqual(item.title, "Başlık")
        self.assertEqual(item.url, "https://example.com/haber")
        self.assertEqual((item.source_id, item.source_name, item.topic, item.content_type, item.purpose), ("sample", "Örnek Kaynak", "ekonomi", "article", "current"))
        self.assertEqual(item.published_at, datetime(2026, 9, 29, 17, 2, tzinfo=timezone.utc))

    def test_missing_bad_or_timezone_free_dates_stay_unknown(self):
        for value in ["", "   ", "bu bir tarih değil", "Tue, 29 Sep 2026 20:02:00", "Tue, 29 Sep 2026 20:02:00 -0000"]:
            with self.subTest(value=value):
                self.assertIsNone(parse_publication_date(value))

    def test_same_moment_with_different_offsets_becomes_same_date(self):
        self.assertEqual(parse_publication_date("Tue, 29 Sep 2026 20:02:00 +0300"), parse_publication_date("Tue, 29 Sep 2026 17:02:00 GMT"))

    def test_same_url_from_two_sources_keeps_first_without_mutation(self):
        first = make_item()
        second = replace(first, source_id="other", source_name="İkinci Kaynak", topic="spor", title="Farklı başlık")
        other = make_item("https://example.com/other")
        original = [first, second, other]
        self.assertEqual(remove_duplicates(original), [first, other])
        self.assertEqual(len(original), 3)

    def test_distinct_query_parameters_and_same_titles_are_not_merged(self):
        first = make_item("https://example.com/watch?v=1")
        second = make_item("https://example.com/watch?v=2")
        self.assertEqual(remove_duplicates([first, second]), [first, second])

    def test_empty_input(self):
        self.assertEqual(remove_duplicates([]), [])

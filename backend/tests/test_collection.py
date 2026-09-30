"""Çoklu akışta tekrarlar ve kısmi kaynak hataları; ağ bağlantısı yok."""

import unittest
from unittest.mock import patch

from backend.app.models import Source
from backend.app.services.collection import collect_contents
from backend.app.sources.rss import RssError


FIRST = Source("first", "Birinci", "https://example.com/first.rss", "ekonomi")
SECOND = Source("second", "İkinci", "https://example.com/second.rss", "spor")


def feed(*links):
    items = ''.join(f'<item><title>Örnek</title><link>{link}</link></item>' for link in links)
    return f'<rss version="2.0"><channel>{items}</channel></rss>'.encode("utf-8")


def responses(download, *values):
    by_url = dict(zip([FIRST.feed_url, SECOND.feed_url], values))
    def read(url):
        value = by_url[url]
        if isinstance(value, Exception):
            raise value
        return value
    download.side_effect = read


class CollectionTests(unittest.TestCase):
    @patch("backend.app.services.collection.download_rss")
    def test_duplicates_within_and_between_feeds(self, download):
        responses(download, *[feed("https://example.com/a", "https://example.com/a"), feed("https://example.com/a", "https://example.com/b")])
        result = collect_contents([FIRST, SECOND])
        self.assertEqual(result.source_counts, {"first": 2, "second": 2})
        self.assertEqual(result.duplicate_count, 2)
        self.assertEqual([item.url for item in result.items], ["https://example.com/a", "https://example.com/b"])
        self.assertEqual(result.items[0].source_id, "first")
        self.assertEqual(result.errors, {})

    @patch("backend.app.services.collection.download_rss")
    def test_failed_feed_does_not_discard_good_feed(self, download):
        responses(download, *[RssError("Bağlantı hatası"), feed("https://example.com/b")])
        result = collect_contents([FIRST, SECOND])
        self.assertEqual(result.source_counts, {"second": 1})
        self.assertEqual(result.errors, {"first": "Bağlantı hatası"})
        self.assertEqual(result.items[0].source_id, "second")

    @patch("backend.app.services.collection.download_rss")
    def test_html_error_page_is_reported_and_next_feed_is_read(self, download):
        responses(download, *[b'<html/>', feed("https://example.com/b")])
        result = collect_contents([FIRST, SECOND])
        self.assertIn("first", result.errors)
        self.assertEqual(len(result.items), 1)

    @patch("backend.app.services.collection.download_rss")
    def test_all_failed_feeds_are_distinct_from_empty_successful_feed(self, download):
        responses(download, *[RssError("Hata"), RssError("Hata")])
        failed = collect_contents([FIRST, SECOND])
        self.assertEqual(failed.source_counts, {})
        self.assertEqual(len(failed.errors), 2)
        self.assertEqual(failed.items, [])
        responses(download, *[feed()])
        empty = collect_contents([FIRST])
        self.assertEqual(empty.source_counts, {"first": 0})
        self.assertEqual(empty.errors, {})

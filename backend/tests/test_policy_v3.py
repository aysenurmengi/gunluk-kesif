from dataclasses import replace
from datetime import date, datetime, timezone, timedelta
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
import unittest
from backend.app.models import ContentItem
from backend.app.services.daily import serialize, get_daily
from backend.app.services.recommendation_policy import prepare_candidate, select_items, topic_shortfalls
from backend.app.services.content import canonical_url
from backend.app.services.collection import CollectionResult
from backend.app.repositories import daily as repo

DAY = date(2026, 9, 30)
def row(n, topic="teknoloji", kind="article", publisher=None, scope=""):
    return ContentItem(f"Yapay zeka nasıl çalışır? {n}", f"https://example.org/{n}", "source", "Kaynak", topic, kind, "current",
                       datetime(2026, 9, 29, tzinfo=timezone.utc), publisher_id=publisher or f"publisher-{n}",
                       recommendation_reason="İnceleme", recommendation_kind="timely", editorial_reviewed=True, news_scope=scope)

class ExpandedPolicyTests(unittest.TestCase):
    def test_finance_and_macro_economy_are_distinct(self):
        self.assertEqual(prepare_candidate(replace(row(1), title="Bileşik faiz nedir? Fon ve portföy rehberi")).topic, "finans")
        self.assertEqual(prepare_candidate(replace(row(2), title="Enflasyon ve işsizlik neden artıyor?")).topic, "ekonomi")

    def test_sports_news_stays_in_sports_and_has_seven_day_window(self):
        item = prepare_candidate(replace(row(1, "spor", "news"), title="Basketbol liginde sezon başlıyor", published_at=datetime(2026, 9, 24, tzinfo=timezone.utc)))
        self.assertEqual(item.topic, "spor")
        self.assertEqual(len(select_items([serialize(item)], DAY)), 1)
        self.assertEqual(select_items([serialize(replace(item, published_at=datetime(2026, 9, 22, tzinfo=timezone.utc)))], DAY), [])

    def test_sports_mix_includes_news_and_learning_with_retained_cards(self):
        kept = [serialize(row(1, "spor")), serialize(row(2, "spor"))]
        new = serialize(row(3, "spor", "news"))
        result = select_items([new], DAY, retained=kept)
        self.assertEqual(len(result), 3)
        self.assertEqual(sum(i["content_type"] == "news" for i in result), 1)

    def test_news_balances_regions_and_publishers(self):
        items = [serialize(row(n, "guncel", "news", "trt" if n < 6 else "bbc", "turkiye" if n < 6 else "dunya")) for n in range(12)]
        chosen = select_items(items, DAY)
        self.assertEqual(len(chosen), 6)
        self.assertEqual(sum(i["news_scope"] == "turkiye" for i in chosen), 3)
        self.assertEqual(sum(i["publisher_id"] == "bbc" for i in chosen), 3)

    def test_diverse_publisher_is_preferred_over_second_item_from_same_publisher(self):
        items = [serialize(row(1, publisher="one")), serialize(row(2, publisher="one")), serialize(row(3, publisher="two"))]
        self.assertEqual({i["publisher_id"] for i in select_items(items, DAY)}, {"one", "two"})

    def test_shortfall_reports_missing_items_without_fabricating_or_repeating(self):
        chosen = select_items([serialize(row(1))] * 3, DAY)
        self.assertEqual(len(chosen), 1)
        self.assertEqual(topic_shortfalls(chosen, ["teknoloji", "finans"]), {"teknoloji": 1, "finans": 2})

    def test_bbc_tracking_does_not_create_duplicate_recommendations(self):
        url = "https://www.bbc.com/turkce/articles/example"
        self.assertEqual(canonical_url(url + "?at_medium=RSS&at_campaign=rss"), url)

    def test_incomplete_day_can_be_completed_after_retry_interval(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "test.sqlite3"
            with patch("backend.app.services.daily.today", return_value=DAY), patch("backend.app.services.daily.collect_contents", return_value=CollectionResult([], {}, {}, 0)) as collect, patch("backend.app.services.daily.curated_items", return_value=[row(1)]) as library:
                initial = get_daily(DAY, path)
                initial["generated_at"] = (datetime.now(timezone.utc) - timedelta(minutes=16)).isoformat()
                with repo.connect(path) as db: repo.save_edition(db, initial)
                library.return_value = [row(1), row(2)]
                updated = get_daily(DAY, path)
                self.assertEqual(len(updated["items"]), 2)
                self.assertIn(initial["items"][0], updated["items"])
                self.assertNotIn("teknoloji", updated["topic_shortfalls"])
                self.assertEqual(collect.call_count, 2)

    def test_legacy_domestic_news_gets_scope_during_selection(self):
        old = serialize(replace(row(1, "guncel", "news"), source_id="trt-guncel"))
        self.assertEqual(select_items([old], DAY)[0]["news_scope"], "turkiye")

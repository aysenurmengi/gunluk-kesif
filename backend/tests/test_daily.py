"""Kalıcı günlük öneri davranışı; ağ yok, gerçek geçici SQLite var."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.models import ContentItem
from backend.app.services.collection import CollectionResult
from backend.app.services.daily import get_daily, select_items, serialize, CollectionUnavailable, TURKEY_TIME
from backend.app.repositories import daily as repo, database

DAY = date(2026, 9, 30)
def item(n, topic="ekonomi", kind="blog", published=None):
    return ContentItem(f"Yazı {n}", f"https://example.com/{n}", f"source-{n % 2}", "Kaynak", topic, kind, "evergreen", published, publisher_id=f"publisher-{n % 2}", recommendation_reason="Açıklayıcı örnek", recommendation_kind="foundation", editorial_reviewed=True)

class DailyTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "daily.sqlite3"
        self.collect = patch("backend.app.services.daily.collect_contents", return_value=CollectionResult([], {"test": 0}, {}, 0)).start()
        self.curated = patch("backend.app.services.daily.curated_items", return_value=[item(n) for n in range(6)]).start()
        self.clock = patch("backend.app.services.daily.today", return_value=DAY).start()
        self.addCleanup(patch.stopall)

    def test_same_day_survives_new_connection_without_network(self):
        first = get_daily(DAY, self.db)
        self.collect.reset_mock()
        self.curated.return_value = [item(99)]
        self.assertEqual(get_daily(DAY, self.db), first)
        self.collect.assert_not_called()

    def test_next_day_uses_different_urls_and_archive_is_unchanged(self):
        first = get_daily(DAY, self.db)
        tomorrow = date(2026, 10, 1)
        self.clock.return_value = tomorrow
        second = get_daily(tomorrow, self.db)
        self.assertEqual(len(first["items"]), 2)
        self.assertEqual(len(second["items"]), 2)
        self.assertFalse({i["url"] for i in first["items"]} & {i["url"] for i in second["items"]})
        self.assertEqual(get_daily(DAY, self.db), first)

    def test_missing_past_does_not_generate_or_fetch(self):
        self.assertIsNone(get_daily(date(2026, 9, 29), self.db))
        self.collect.assert_not_called()
        with repo.connect(self.db) as db:
            self.assertEqual(repo.list_dates(db), [])

    def test_pool_retains_items_that_disappear_from_feed(self):
        get_daily(DAY, self.db)
        self.curated.return_value = []
        self.clock.return_value = date(2026, 10, 1)
        self.assertEqual(len(get_daily(self.clock.return_value, self.db)["items"]), 2)

    def test_exhausted_pool_does_not_repeat(self):
        self.curated.return_value = [item(0)]
        get_daily(DAY, self.db)
        self.clock.return_value = date(2026, 10, 1)
        self.assertEqual(get_daily(self.clock.return_value, self.db)["items"], [])

    def test_empty_failure_is_retryable_not_saved(self):
        self.curated.return_value = []
        self.collect.return_value = CollectionResult([], {}, {"test": "Kesinti"}, 0)
        with self.assertRaises(CollectionUnavailable):
            get_daily(DAY, self.db)
        with repo.connect(self.db) as db:
            self.assertEqual(repo.list_dates(db), [])
        self.curated.return_value = [item(1)]
        self.assertEqual(len(get_daily(DAY, self.db)["items"]), 1)

    def test_concurrent_requests_create_one_identical_edition(self):
        # Şema önceden hazır; iki isteğin seçim işlemi aynı anda başlayabilir.
        with repo.connect(self.db): pass
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: get_daily(DAY, self.db), range(2)))
        self.assertEqual(results[0], results[1])
        with repo.connect(self.db) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM recommendations").fetchone()[0], 2)

    def test_daily_api_archive_future_and_validation(self):
        with patch.object(database, "DATABASE", self.db), patch("backend.app.api.daily_routes.today", return_value=DAY), TestClient(app) as client:
            response = client.get("/api/recommendations")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["available_dates"], [DAY.isoformat()])
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertEqual(client.get("/api/recommendations?day=2026-09-29").status_code, 404)
            self.assertEqual(client.get("/api/recommendations?day=2026-10-01").status_code, 400)
            self.assertEqual(client.get("/api/recommendations?day=oops").status_code, 422)

class SelectionTests(unittest.TestCase):
    def test_recent_news_and_topic_news_as_development(self):
        candidates = [item(1, "guncel", "news", datetime(2026, 9, 29, tzinfo=timezone.utc)),
                      item(2, "guncel", "news", datetime(2026, 9, 30, tzinfo=timezone.utc)),
                      item(3, "guncel", "news", datetime(2026, 9, 20, tzinfo=timezone.utc)),
                      # Konusu belli haber akışı (TRT Ekonomi) o konunun "gelişme" adayıdır.
                      item(4, "ekonomi", "news", datetime(2026, 9, 30, tzinfo=timezone.utc)),
                      item(5, "ekonomi", "news", datetime(2026, 9, 25, tzinfo=timezone.utc))]
        selected = select_items([serialize(i) for i in candidates], DAY)
        self.assertEqual({i["url"] for i in selected}, {candidates[0].url, candidates[1].url, candidates[3].url})

    def test_video_diversity_and_old_learning_material(self):
        candidates = [item(1), item(2), item(3, kind="video", published=datetime(2015, 1, 1, tzinfo=timezone.utc))]
        selected = select_items([serialize(i) for i in candidates], DAY)
        self.assertEqual({i["content_type"] for i in selected}, {"blog", "video"})

    def test_future_publication_is_not_recommended(self):
        self.assertEqual(select_items([serialize(item(1, published=datetime(2027, 1, 1, tzinfo=timezone.utc)))], DAY), [])

    def test_turkish_date_rolls_before_utc_midnight(self):
        self.assertEqual(datetime(2026, 9, 29, 22, tzinfo=timezone.utc).astimezone(TURKEY_TIME).date(), DAY)

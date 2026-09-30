"""Kelime başı eşleştirme, havuz temizliği ve bekletmeyen tamamlama."""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
from backend.app.models import ContentItem
from backend.app.repositories import daily as repo
from backend.app.services.collection import CollectionResult
from backend.app.services.daily import get_daily, serialize
from backend.app.services.recommendation_policy import expired, has_term, normalized, prepare_candidate

DAY = date(2026, 9, 30)
def article(title, n=1, published=datetime(2026, 9, 29, tzinfo=timezone.utc)):
    return ContentItem(title, f"https://example.org/{n}", "general", "Genel", "", "article", "current", published)

class WordMatchingTests(unittest.TestCase):
    def test_substrings_inside_other_words_do_not_match(self):
        for text, term in [("telefon", "fon"), ("yeni kural getirildi", "getiri"), ("gümrük tarifeleri", "tarif"),
                           ("romanya seçimleri", "roman"), ("türkçe dersleri", "türk"), ("koşullar", "koşu")]:
            with self.subTest(text=text):
                self.assertFalse(has_term(text, term))

    def test_turkish_suffixes_still_match(self):
        for text, term in [("romanın dili", "roman"), ("fonların getirisi", "fon"), ("fonların getirisi", "getiri"),
                           ("tarifi", "tarif"), ("türkiye", "türk"), ("merkez bankası kararı", "merkez bankası")]:
            with self.subTest(text=text):
                self.assertTrue(has_term(text, term))

    def test_false_friend_titles_are_not_misfiled(self):
        self.assertIsNone(prepare_candidate(article("Telefon bataryası nasıl çalışır?")))
        self.assertIsNone(prepare_candidate(article("Gümrük tarifeleri neden arttı?")))
        self.assertEqual(prepare_candidate(article("Makroekonomi nedir?")).topic, "ekonomi")

    def test_turkish_uppercase_i(self):
        self.assertEqual(normalized("YAPAY ZEKA NASIL ÇALIŞIR"), "yapay zeka nasıl çalışır")
        self.assertEqual(prepare_candidate(article("YAPAY ZEKA NASIL ÇALIŞIR?")).topic, "teknoloji")

class ExpiryTests(unittest.TestCase):
    def test_expiry_matches_eligibility_windows(self):
        news = serialize(replace(prepare_candidate(replace(article("Haber"), content_type="news", topic="guncel")),
                                 published_at=datetime(2026, 9, 26, tzinfo=timezone.utc)))
        self.assertTrue(expired(news, DAY))
        self.assertFalse(expired({**news, "published_at": "2026-09-28T00:00:00+00:00"}, DAY))
        future = serialize(replace(prepare_candidate(article("Yapay zeka nedir?")), published_at=datetime(2026, 10, 5, tzinfo=timezone.utc)))
        self.assertFalse(expired(future, DAY))
        foundation = {**future, "recommendation_kind": "foundation", "editorial_reviewed": True, "published_at": None}
        self.assertFalse(expired(foundation, DAY))
        self.assertTrue(expired({**foundation, "editorial_reviewed": False}, DAY))
        self.assertTrue(expired({"url": "https://old.example/", "topic": "kitap", "content_type": "article"}, DAY))

class PoolAndRefreshTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "pool.sqlite3"
        self.collect = patch("backend.app.services.daily.collect_contents", return_value=CollectionResult([], {"ok": 0}, {}, 0)).start()
        self.curated = patch("backend.app.services.daily.curated_items", return_value=[]).start()
        patch("backend.app.services.daily.today", return_value=DAY).start()
        self.addCleanup(patch.stopall)

    def pool_urls(self):
        with repo.connect(self.db) as db:
            return {row[0] for row in db.execute("SELECT url FROM pool")}

    def test_expired_and_misfiled_pool_rows_are_removed(self):
        fresh = serialize(prepare_candidate(article("Yapay zeka nedir?", 1)))
        stale = {**fresh, "url": "https://example.org/old", "published_at": "2025-01-01T00:00:00+00:00"}
        # Eski eşleştiricinin "telefon" yüzünden Finans'a koyduğu kayıt.
        misfiled = {**fresh, "url": "https://example.org/phone", "title": "Telefon bataryası nasıl çalışır?", "topic": "finans"}
        with repo.connect(self.db) as db:
            repo.store_candidates(db, [fresh, stale, misfiled])
        edition = get_daily(DAY, self.db)
        self.assertEqual([i["url"] for i in edition["items"]], [fresh["url"]])
        self.assertEqual(self.pool_urls(), {fresh["url"]})

    def test_request_path_returns_current_cards_and_completes_in_background(self):
        first = serialize(prepare_candidate(article("Yapay zeka nedir?", 1)))
        with repo.connect(self.db) as db:
            repo.store_candidates(db, [first])
        initial = get_daily(DAY, self.db)
        self.assertEqual(initial["topic_shortfalls"]["teknoloji"], 1)
        initial["generated_at"] = (datetime.now(timezone.utc) - timedelta(minutes=16)).isoformat()
        with repo.connect(self.db) as db:
            repo.save_edition(db, initial)

        release = threading.Event()
        second = replace(prepare_candidate(article("Robot nasıl öğrenir?", 2)), url="https://other.example/2")
        def slow_collect(_sources):
            release.wait(5)
            return CollectionResult([second], {"ok": 1}, {}, 0)
        self.collect.side_effect = slow_collect

        # Kaynaklar yavaş olsa da istek mevcut kartlarla hemen döner.
        self.assertEqual(get_daily(DAY, self.db, wait_for_refresh=False), initial)
        release.set()
        for thread in threading.enumerate():
            if thread.name == f"daily-refresh-{DAY}":
                thread.join(5)
        updated = get_daily(DAY, self.db)
        self.assertEqual(len(updated["items"]), 2)
        self.assertNotIn("teknoloji", updated["topic_shortfalls"])
        self.assertEqual(self.collect.call_count, 2)

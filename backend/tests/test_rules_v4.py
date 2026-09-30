"""Kaynak profili, rol ve kalite puanı kuralları (30.09.2026 etiketlerinden çıkan örnekler)."""
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from backend.app.models import ContentItem, SourceProfile
from backend.app.repositories import daily as repo
from backend.app.services.collection import CollectionResult
from backend.app.services.daily import get_daily, serialize
from backend.app.services.recommendation_policy import POLICY_VERSION, prepare_candidate, select_items
from backend.app.sources.daily_catalog import CATALOG_REVISION

DAY = date(2026, 9, 30)
BILIM = SourceProfile(("bilim",), 3)
KITAP = SourceProfile(("kitap",), 2)
TEKNOLOJI = SourceProfile(("teknoloji",), 2)
LONG = "Uzun bir açıklama metni; " * 8


def item(title, description=LONG, kind="article", n=1, source="kaynak", day=29):
    return ContentItem(title, f"https://ornek{n}.example/{n}", source, "Kaynak", "", kind, "current",
                       datetime(2026, 9, day, tzinfo=timezone.utc), description)


class ProfileTests(unittest.TestCase):
    def test_review_without_keyword_in_title_uses_source_and_description(self):
        review = prepare_candidate(item("Bir Kedinin Gözünden İnsanlığı Sorgulamak: Frankie",
                                        "Hemen her yerde karşımıza çıkan kedilerin dilinden bir kitap okudum. " + LONG), KITAP)
        self.assertEqual(review.topic, "kitap")

    def test_profile_alone_does_not_assign_topic(self):
        # Kitap sitesindeki konu dışı bir yazı kitap önerisi değildir.
        self.assertIsNone(prepare_candidate(item("Cildinizin Mevsim Geçişi Rehberi", "Hava serinledikçe cildimiz değişir. " + LONG), KITAP))
        self.assertIsNone(prepare_candidate(item("İlişkilerde Bağlanma Stilleri Ne Anlatıyor?"), KITAP))

    def test_science_and_technology_are_separate(self):
        self.assertEqual(prepare_candidate(item("Kasırganın merkezi neden güneşli olur?", kind="video"), BILIM).topic, "bilim")
        self.assertEqual(prepare_candidate(item("Mitokondriler nasıl enerji üretir?"), BILIM).topic, "bilim")
        self.assertEqual(prepare_candidate(item("OpenAI yeni yapay zeka modelini tanıttı"), TEKNOLOJI).topic, "teknoloji")
        # Bilim kaynağındaki yazı, başlıkta teknoloji ağır basıyorsa teknolojiye gider.
        self.assertEqual(prepare_candidate(item("Sağlıkta yapay zeka: robot ve algoritma kararları nasıl veriyor?"), BILIM).topic, "teknoloji")

    def test_negative_signals(self):
        self.assertIsNone(prepare_candidate(item("Jeeves, 110 milyon dolar yatırım aldı"), TEKNOLOJI))
        self.assertIsNone(prepare_candidate(item("Altın fiyatlarında son durum"), SourceProfile(("finans",), 2)))
        # "Burç" bir ad olabilir; yalnızca burç yorumu elenir.
        review = prepare_candidate(item("Burç Aksoy'un yeni romanı üzerine"), KITAP)
        self.assertEqual(review.topic, "kitap")
        self.assertIsNone(prepare_candidate(item("Akrep burcu yorumu: bu ay okunacak romanlar"), KITAP))

    def test_roles(self):
        self.assertEqual(prepare_candidate(item("Kuskus nasıl pişirilir? Tane tane olmasının sırrı", kind="video"),
                                           SourceProfile(("yemek",), 2)).role, "video")
        self.assertEqual(prepare_candidate(item("OpenAI yeni yapay zeka modelini tanıttı"), TEKNOLOJI).role, "gelisme")
        self.assertEqual(prepare_candidate(item("Yapay zeka kasırgaları neden tahmin edemiyor?"), TEKNOLOJI).role, "derinlik")

    def test_high_tier_source_outranks_low_tier(self):
        strong = prepare_candidate(item("Yapay zeka neden yanılıyor?"), SourceProfile(("teknoloji",), 3))
        weak = prepare_candidate(item("Yapay zeka neden yanılıyor?"), SourceProfile(("teknoloji",), 1))
        self.assertGreater(strong.quality, weak.quality)


class MixTests(unittest.TestCase):
    def test_topic_mix_takes_one_of_each_role(self):
        profile = SourceProfile(("teknoloji",), 3)
        rows = [prepare_candidate(item(f"Yapay zeka nasıl çalışır? {n}", n=n), profile) for n in range(1, 4)]
        rows.append(prepare_candidate(item("Yapay zeka neden unutur?", kind="video", n=4), profile))
        rows.append(prepare_candidate(item("OpenAI yeni yapay zeka modelini tanıttı: neden önemli?", n=5), profile))
        chosen = select_items([serialize(r) for r in rows], DAY)
        self.assertEqual(sorted(c["role"] for c in chosen), ["derinlik", "gelisme", "video"])

    def test_weak_development_does_not_jump_ahead_of_strong_articles(self):
        strong = [prepare_candidate(item(f"Yapay zeka nasıl öğrenir? {n}", n=n), SourceProfile(("teknoloji",), 3)) for n in range(1, 4)]
        weak = prepare_candidate(item("Meta kurumsal yapay zeka platformunu duyurdu", n=9), SourceProfile(("teknoloji",), 2))
        self.assertIsNotNone(weak)
        chosen = select_items([serialize(r) for r in (*strong, weak)], DAY)
        self.assertNotIn(weak.url, [c["url"] for c in chosen])

    def test_development_older_than_a_week_expires(self):
        news = prepare_candidate(item("OpenAI yeni modelini tanıttı: yapay zeka", day=20), TEKNOLOJI)
        self.assertEqual(news.role, "gelisme")
        self.assertEqual(select_items([serialize(news)], DAY), [])
        self.assertEqual(len(select_items([serialize(replace(news, published_at=datetime(2026, 9, 25, tzinfo=timezone.utc)))], DAY)), 1)


class RemovedTopicTests(unittest.TestCase):
    def test_removed_topic_is_neither_retained_nor_recommended(self):
        moda_card = {**serialize(prepare_candidate(item("Kitap nasıl okunur?", n=1), KITAP)), "topic": "moda"}
        moda_pool = {**serialize(prepare_candidate(item("Roman nasıl yazılır?", n=2), KITAP)), "topic": "moda",
                     "editorial_reviewed": True, "recommendation_kind": "foundation"}
        with TemporaryDirectory() as temp:
            path = Path(temp) / "test.sqlite3"
            old = {"date": DAY.isoformat(), "items": [moda_card], "sources": [], "errors": {},
                   "generated_at": "old", "policy_version": POLICY_VERSION, "catalog_revision": CATALOG_REVISION - 1}
            with repo.connect(path) as db:
                repo.save_edition(db, old)
                repo.store_candidates(db, [moda_pool])
            with patch("backend.app.services.daily.today", return_value=DAY), \
                    patch("backend.app.services.daily.collect_contents", return_value=CollectionResult([], {"ok": 0}, {}, 0)), \
                    patch("backend.app.services.daily.curated_items", return_value=[]):
                updated = get_daily(DAY, path)
            self.assertNotIn("moda", {i["topic"] for i in updated["items"]})
            self.assertNotIn("moda", updated["supported_topics"])
            with repo.connect(path) as db:
                self.assertNotIn(moda_pool["url"], [row[0] for row in db.execute("SELECT url FROM pool")])

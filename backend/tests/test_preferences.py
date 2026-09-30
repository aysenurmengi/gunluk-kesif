"""Örnek tercihler, yayıncı çeşitliliği, güncellik ve sürüm geçişi."""
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
from backend.app.models import ContentItem
from backend.app.services.content import canonical_url, normalize_article
from backend.app.services.daily import serialize, get_daily
from backend.app.services.recommendation_policy import prepare_candidate, select_items, POLICY_VERSION
from backend.app.sources.rss import parse_rss
from backend.app.sources.daily_catalog import FEED_SOURCES, curated_items
from backend.app.services.collection import CollectionResult
from backend.app.repositories import daily as repo

DAY = date(2026, 9, 30)
def candidate(number=1, **changes):
    base = ContentItem("Yapay zekâ nasıl çalışır?", f"https://example.com/{number}", "general", "Genel yayıncı", "kitap", "article", "current", datetime(2026, 9, 29, tzinfo=timezone.utc))
    return replace(base, **changes)

class PreferenceTests(unittest.TestCase):
    def test_topic_belongs_to_content_not_publisher(self):
        tech = prepare_candidate(candidate())
        economy = prepare_candidate(candidate(2, title="Finansal kriz nasıl ortaya çıkar?"))
        self.assertEqual(tech.topic, "teknoloji")
        self.assertEqual(economy.topic, "ekonomi")
        self.assertEqual(tech.publisher_id, economy.publisher_id)

    def test_unrelated_content_from_same_source_is_rejected(self):
        self.assertIsNone(prepare_candidate(candidate(title="Bahar konseri biletleri satışta")))

    def test_one_publisher_can_fill_minimum_when_no_alternative_exists(self):
        items = [prepare_candidate(candidate()), prepare_candidate(candidate(2, source_id="other-feed"))]
        self.assertEqual(len(select_items([serialize(i) for i in items], DAY)), 2)

    def test_two_distinct_publishers_can_fill_same_topic(self):
        items = [prepare_candidate(candidate()), prepare_candidate(candidate(2, url="https://another.example/a"))]
        self.assertEqual(len(select_items([serialize(i) for i in items], DAY)), 2)

    def test_old_technology_article_is_not_evergreen_by_source_label(self):
        old = candidate(published_at=datetime(2018, 1, 1, tzinfo=timezone.utc), purpose="evergreen")
        self.assertEqual(select_items([serialize(prepare_candidate(old))], DAY), [])

    def test_market_commentary_expires_after_seven_days(self):
        old = candidate(title="Piyasalar neden düşüyor?", published_at=datetime(2026, 9, 22, tzinfo=timezone.utc))
        self.assertEqual(select_items([serialize(prepare_candidate(old))], DAY), [])
        recent = replace(old, published_at=datetime(2026, 9, 23, tzinfo=timezone.utc))
        self.assertEqual(len(select_items([serialize(prepare_candidate(recent))], DAY)), 1)

    def test_unknown_date_cannot_pass_timely_filter(self):
        unknown = prepare_candidate(candidate(published_at=None))
        self.assertEqual(select_items([serialize(unknown)], DAY), [])

    def test_foundation_requires_explicit_review(self):
        value = prepare_candidate(candidate(published_at=datetime(2018, 1, 1, tzinfo=timezone.utc)))
        value = replace(value, recommendation_kind="foundation")
        self.assertEqual(select_items([serialize(value)], DAY), [])
        self.assertEqual(len(select_items([serialize(replace(value, editorial_reviewed=True))], DAY)), 1)

    def test_user_examples_have_two_economy_publishers_and_distinct_intents(self):
        picked = select_items([serialize(i) for i in curated_items()], DAY)
        economy = [i for i in picked if i["topic"] == "ekonomi"]
        self.assertEqual(len(economy), 2)
        self.assertEqual(len({i["publisher_id"] for i in economy}), 2)
        self.assertEqual({i["recommendation_kind"] for i in economy}, {"timely", "foundation"})

    def test_youtube_tracking_urls_are_the_same_content(self):
        self.assertEqual(canonical_url("https://youtu.be/Fl8iktUZtuU?si=abc"), canonical_url("https://www.youtube.com/watch?v=Fl8iktUZtuU&feature=share"))
        self.assertNotEqual(canonical_url("https://example.com/?a=1"), canonical_url("https://example.com/?a=2"))

    def test_old_pool_record_without_review_or_reason_is_rejected(self):
        self.assertEqual(select_items([serialize(candidate())], DAY), [])

    def test_atom_description_date_and_alternate_link(self):
        data = b'''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/">
          <entry><title>Video</title><link rel="self" href="https://example.com/api"/>
          <link rel="alternate" href="https://www.youtube.com/watch?v=abc"/>
          <published>2026-09-28T14:14:33Z</published>
          <media:group><media:description>Aciklama</media:description></media:group></entry></feed>'''
        row = parse_rss(data)[0]
        item = normalize_article(row, FEED_SOURCES[1])
        self.assertEqual(item.url, "https://www.youtube.com/watch?v=abc")
        self.assertEqual(item.description, "Aciklama")
        self.assertEqual(item.published_at, datetime(2026, 9, 28, 14, 14, 33, tzinfo=timezone.utc))
        self.assertEqual(parse_rss(b'<feed xmlns="http://www.w3.org/2005/Atom"/>'), [])

    def test_rss_description_entities_are_plain_text(self):
        xml = b'<rss><channel><item><title>A</title><link>https://example.com/</link><description>&lt;p&gt;A &amp;amp; B&lt;/p&gt;</description></item></channel></rss>'
        self.assertEqual(parse_rss(xml)[0]["description"], "A & B")

class PolicyUpgradeTests(unittest.TestCase):
    def test_only_today_is_upgraded_and_old_seen_urls_remain_seen(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "test.sqlite3"
            previous = {"date": "2026-09-29", "items": [], "sources": [], "errors": {}, "generated_at": "old"}
            bad = serialize(candidate())
            current = {**previous, "date": DAY.isoformat(), "items": [bad]}
            with repo.connect(path) as db:
                repo.save_edition(db, previous)
                repo.save_edition(db, current)
            with patch("backend.app.services.daily.today", return_value=DAY), patch("backend.app.services.daily.collect_contents", return_value=CollectionResult([], {"ok": 0}, {}, 0)) as collect:
                updated = get_daily(DAY, path)
                self.assertEqual(updated["policy_version"], POLICY_VERSION)
                self.assertNotIn(bad["url"], [i["url"] for i in updated["items"]])
                self.assertEqual(get_daily(date(2026, 9, 29), path), previous)
                self.assertEqual(get_daily(DAY, path), updated)
                self.assertEqual(collect.call_count, 1)
            with repo.connect(path) as db:
                self.assertIn(bad["url"], repo.recommended_urls(db))


class CatalogExpansionTests(unittest.TestCase):
    def test_each_new_topic_has_two_different_publishers(self):
        selected = select_items([serialize(i) for i in curated_items()], DAY)
        for topic in ("yemek", "moda", "kitap", "spor"):
            with self.subTest(topic=topic):
                items = [i for i in selected if i["topic"] == topic]
                self.assertEqual(len(items), 2)
                self.assertEqual(len({i["publisher_id"] for i in items}), 2)

    def test_catalog_upgrade_retains_today_cards_and_past_history(self):
        from backend.app.sources.daily_catalog import CATALOG_REVISION
        with TemporaryDirectory() as temp:
            path = Path(temp) / "test.sqlite3"
            kept = serialize(curated_items()[0])
            old = {"date": DAY.isoformat(), "items": [kept], "sources": [],
                   "errors": {"old-source": "Temporary failure"}, "generated_at": "old", "policy_version": POLICY_VERSION}
            yesterday = {**old, "date": "2026-09-29", "items": []}
            with repo.connect(path) as db:
                repo.save_edition(db, yesterday)
                repo.save_edition(db, old)
            with patch("backend.app.services.daily.today", return_value=DAY), patch("backend.app.services.daily.collect_contents", return_value=CollectionResult([], {"ok": 0}, {}, 0)) as collect:
                updated = get_daily(DAY, path)
                self.assertIn(kept, updated["items"])
                self.assertEqual(updated["catalog_revision"], CATALOG_REVISION)
                self.assertEqual(updated["errors"], {})
                self.assertTrue({"yemek", "moda", "kitap", "spor"}.issubset({i["topic"] for i in updated["items"]}))
                self.assertEqual(get_daily(DAY, path), updated)
                self.assertEqual(get_daily(date(2026, 9, 29), path), yesterday)
                self.assertEqual(collect.call_count, 1)
            with repo.connect(path) as db:
                self.assertEqual(repo.recommended_urls(db).count(kept["url"]), 1)

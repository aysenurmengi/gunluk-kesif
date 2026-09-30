"""Ağ bağlantısı olmadan, dış kaynak verisindeki önemli sınır durumları."""

import unittest

from backend.app.sources.rss import RssError, parse_rss


def feed(items: str) -> bytes:
    return f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>{items}</channel></rss>'.encode("utf-8")


class ParseRssTests(unittest.TestCase):
    def test_turkish_text_entities_and_date_are_preserved(self):
        articles = parse_rss(feed("""<item>
            <title>  Üretim &amp; büyüme  </title>
            <link>https://example.com/haber?a=1&amp;b=2</link>
            <pubDate>Tue, 29 Sep 2026 10:00:00 +0300</pubDate>
        </item>"""))
        self.assertEqual(articles, [{
            "title": "Üretim & büyüme",
            "link": "https://example.com/haber?a=1&b=2",
            "published_at": "Tue, 29 Sep 2026 10:00:00 +0300",
        }])

    def test_missing_date_does_not_become_todays_date(self):
        articles = parse_rss(feed('<item><title>Başlık</title><link>https://example.com/haber</link></item>'))
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["published_at"], "")

    def test_bad_records_do_not_hide_valid_record(self):
        articles = parse_rss(feed("""
            <item><link>https://example.com/no-title</link></item>
            <item><title>Bağlantısız</title></item>
            <item><title>Yerel dosya</title><link>file:///C:/test.txt</link></item>
            <item><title>Göreli bağlantı</title><link>/haber</link></item>
            <item><title>Bozuk URL</title><link>http://[</link></item>
            <item><title>Geçerli</title><link>https://example.com/valid</link></item>
        """))
        self.assertEqual([item["title"] for item in articles], ["Geçerli"])

    def test_empty_channel_is_valid_but_has_no_articles(self):
        self.assertEqual(parse_rss(feed("")), [])

    def test_malformed_xml_has_readable_error(self):
        with self.assertRaisesRegex(RssError, "geçerli bir XML"):
            parse_rss(b'<rss><channel>')

    def test_html_and_missing_channel_are_not_silent_empty_feeds(self):
        for data in [b'<html><body>Error</body></html>', b'<rss/>']:
            with self.subTest(data=data), self.assertRaisesRegex(RssError, "RSS 2.0"):
                parse_rss(data)


if __name__ == "__main__":
    unittest.main()

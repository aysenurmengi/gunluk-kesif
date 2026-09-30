"""Yayıncılar aday sağlar; konu ataması içerik düzeyinde yapılır."""
from datetime import datetime
from ..models import ContentItem, Source, SourceProfile
from .curated_library import LIBRARY_ITEMS

CATALOG_REVISION = 5


def _youtube(channel_id):
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


FEED_SOURCES = (
    Source("evrimagaci", "Evrim Ağacı", "https://evrimagaci.org/rss.xml", ""),
    Source("youtube:UCW4Y4bPuafXwVEs0oly5vdw", "Mesele Ekonomi", "https://www.youtube.com/feeds/videos.xml?channel_id=UCW4Y4bPuafXwVEs0oly5vdw", "", "video"),
    Source("edebiyat-inceleme", "Edebiyat Haber", "https://www.edebiyathaber.net/feed/", ""),
    Source("trt-guncel", "TRT Haber / Gündem", "https://www.trthaber.com/gundem_articles.rss", "guncel", "news", news_scope="turkiye"),
    Source("trt-dunya", "TRT Haber / Dünya", "https://www.trthaber.com/dunya_articles.rss", "guncel", "news", news_scope="dunya"),
    Source("bbc-turkce", "BBC Türkçe", "https://feeds.bbci.co.uk/turkce/rss.xml", "guncel", "news"),
    Source("trt-spor", "TRT Haber / Spor", "https://www.trthaber.com/spor_articles.rss", "spor", "news"),
    Source("matematiksel", "Matematiksel", "https://www.matematiksel.org/feed/", ""),
    # Elle seçilmiş liste tükenmesin diye yemek, kitap ve ekonomi akışları.
    # Konu yine içerik düzeyinde atanır; akıştaki her yazı önerilmez.
    Source("lezzet", "Lezzet", "https://www.lezzet.com.tr/rss", ""),
    Source("kitaphaber", "Kitap Haber", "https://www.kitaphaber.com.tr/rss", ""),
    Source("mahfi-egilmez", "Mahfi Eğilmez", "https://www.mahfiegilmez.com/feeds/posts/default?alt=rss", ""),
    # Her konuda gelişme / video / derinlik karışımı için video ve haber akışları.
    Source("trt-ekonomi", "TRT Haber / Ekonomi", "https://www.trthaber.com/ekonomi_articles.rss", "ekonomi", "news"),
    Source("webrazzi", "Webrazzi", "https://webrazzi.com/feed/", ""),
    Source("youtube:UCv6jcPwFujuTIwFQ11jt1Yw", "Barış Özcan", _youtube("UCv6jcPwFujuTIwFQ11jt1Yw"), "", "video"),
    Source("youtube:UCatnasFAiXUvWwH8NlSdd3A", "Evrim Ağacı (YouTube)", _youtube("UCatnasFAiXUvWwH8NlSdd3A"), "", "video"),
    Source("youtube:UCWA2nh0yrIMC6uG0hfbucRQ", "Yemek.com (YouTube)", _youtube("UCWA2nh0yrIMC6uG0hfbucRQ"), "", "video"),
    Source("youtube:UCvgwLFmnppZoPVBQJwPaNsA", "Socrates Dergi", _youtube("UCvgwLFmnppZoPVBQJwPaNsA"), "", "video"),
    Source("youtube:UCebdo7-2NdjcktKzco64iNw", "TRT Spor (YouTube)", _youtube("UCebdo7-2NdjcktKzco64iNw"), "", "video"),
)
# 30.09.2026'da 240 aday elle etiketlenerek belirlendi (tier: 3 çoğu iyi, 2 karışık,
# 1 çoğu elenir). DW Türkçe (0/15) ve ShiftDelete (0/16) bu yüzden eklenmedi.
# Güncel haber akışlarının profili yoktur; onlar ayrı kurallarla seçilir.
SOURCE_PROFILES = {
    "evrimagaci": SourceProfile(("bilim",), 3),
    "youtube:UCatnasFAiXUvWwH8NlSdd3A": SourceProfile(("bilim",), 3),
    "youtube:UCv6jcPwFujuTIwFQ11jt1Yw": SourceProfile(("teknoloji", "bilim"), 3),
    "matematiksel": SourceProfile(("bilim",), 3),
    # Yatırım turu duyuruları NEGATIVE_TERMS ile elendiği için kalanı orta seviyede.
    "webrazzi": SourceProfile(("teknoloji",), 2),
    "mahfi-egilmez": SourceProfile(("ekonomi", "finans"), 3),
    "youtube:UCW4Y4bPuafXwVEs0oly5vdw": SourceProfile(("finans", "ekonomi"), 3),
    "trt-ekonomi": SourceProfile(("ekonomi",), 2),
    "edebiyat-inceleme": SourceProfile(("kitap",), 2),
    "kitaphaber": SourceProfile(("kitap",), 2),
    "lezzet": SourceProfile(("yemek",), 1),
    "youtube:UCWA2nh0yrIMC6uG0hfbucRQ": SourceProfile(("yemek",), 2),
    "youtube:UCvgwLFmnppZoPVBQJwPaNsA": SourceProfile(("spor",), 3),
    "youtube:UCebdo7-2NdjcktKzco64iNw": SourceProfile(("spor",), 1),
    "trt-spor": SourceProfile(("spor",), 2),
}
CURATED_SOURCES = (
    Source("youtube:UCDTSUkdlbcgEU-IGH_mHgmw", "Bebar Bilim", "https://www.youtube.com/@bebarbilim", "", "video"),
)
# Elle seçilen yazıların yayıncıları da API kaynak listesinde görünür.
_known_sources = {source.id for source in (*FEED_SOURCES, *CURATED_SOURCES)}
CURATED_SOURCES += tuple(
    Source(row["source_id"], row["source_name"], row["url"], "", row["content_type"])
    for row in LIBRARY_ITEMS if row["source_id"] not in _known_sources
)
SUPPORTED_TOPICS = ("teknoloji", "bilim", "ekonomi", "finans", "kitap", "guncel", "yemek", "spor")

# Kullanıcının örnekleri tercih referansıdır. Buradaki kısa açıklamalar
# editoryal nottur; video transkripti veya otomatik üretilmiş özet değildir.
REFERENCE_ITEMS = (
    dict(title="Şehirler Bizi Boğuyor! Peki Nerede Hata Yaptık?",
         url="https://www.youtube.com/watch?v=Fl8iktUZtuU",
         source_id="youtube:UCDTSUkdlbcgEU-IGH_mHgmw", source_name="Bebar Bilim",
         publisher_id="youtube:UCDTSUkdlbcgEU-IGH_mHgmw", topic="teknoloji",
         content_type="video", purpose="evergreen", recommendation_kind="foundation",
         published_at="2026-09-27T12:46:21+00:00",
         recommendation_reason="Verdiğin örneklerden: şehir tasarımının günlük yaşamla ilişkisini ele alan açıklayıcı bir video."),
    dict(title="Piyasalar Tepetaklak! Kritik Gün Geldi & Borsayı Zor Günler Bekliyor | Atilla Yeşilada",
         url="https://www.youtube.com/watch?v=hafKC_a0t7U",
         source_id="youtube:UCW4Y4bPuafXwVEs0oly5vdw", source_name="Mesele Ekonomi",
         publisher_id="youtube:UCW4Y4bPuafXwVEs0oly5vdw", topic="finans",
         content_type="video", purpose="current", recommendation_kind="timely",
         published_at="2026-09-28T14:14:33+00:00",
         recommendation_reason="Verdiğin örneklerden: güncel piyasa değerlendirmesi. Bu tür yorumları yalnızca ilk 7 gün içinde öneriyoruz."),
    dict(title="2008 Finansal Krizi: Dünya Ekonomisi, Ev Kredisi Balonunun Patlamasıyla Nasıl Diz Çöktü?",
         url="https://evrimagaci.org/2008-finansal-krizi-dunya-ekonomisi-ev-kredisi-balonunun-patlamasiyla-nasil-diz-coktu-9452",
         source_id="evrimagaci", source_name="Evrim Ağacı", publisher_id="evrimagaci.org",
         topic="ekonomi", content_type="article", purpose="evergreen", recommendation_kind="foundation",
         published_at="2021-02-05T00:00:00+03:00", publication_date_only=True,
         recommendation_reason="Verdiğin örneklerden: 2008 krizinin nedenlerini açıklıyor. Eski bir piyasa tahmini değil, ekonomik tarih anlatımı."),
)

def curated_items():
    return [ContentItem(**{
        "purpose": "evergreen" if row["recommendation_kind"] == "foundation" else "current",
        **row,
        "published_at": datetime.fromisoformat(row["published_at"]) if row["published_at"] else None,
        "editorial_reviewed": True,
        # Elle incelenmiş içerik: rolü türünden gelir, kalitesi yüksek kabul edilir.
        "role": "video" if row["content_type"] == "video" else "derinlik",
        "quality": 8,
    }) for row in (*REFERENCE_ITEMS, *LIBRARY_ITEMS)]

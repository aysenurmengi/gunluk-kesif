"""Tercih örneklerinden yazılmış açık kurallar. Öğrenilmiş bir AI modeli değil."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import re
from urllib.parse import urlsplit
from .content import canonical_url

POLICY_VERSION = 4
MIN_ITEMS_PER_TOPIC = 2
# Konu başına hedef: bir gelişme, bir video, bir derinlemesine yazı.
DEFAULT_DAILY_TARGET = 3
DAILY_TARGETS = {"guncel": 6}
ROLES = ("gelisme", "video", "derinlik")
TURKEY_TIME = timezone(timedelta(hours=3))
# Model/haber/piyasa bilgisinin yaşlanma hızı farklıdır.
MAX_AGE_DAYS = {"teknoloji": 30, "bilim": 60, "ekonomi": 30, "finans": 7, "kitap": 60, "yemek": 60, "spor": 30}
NEWS_MAX_AGE_DAYS = {"guncel": 3, "spor": 7, "ekonomi": 3}
# "Gelişme" rolündeki haber dışı içerik de bir hafta içinde eskir.
DEVELOPMENT_MAX_AGE_DAYS = 7
TOPIC_TERMS = {
    "teknoloji": ("yapay zeka", "dil modeli", "gpt", "chatgpt", "openai", "robot", "yazılım", "şehir", "teknoloji",
                  "mühendis", "çip", "işlemci", "algoritma", "internet", "agent", "siber", "otonom",
                  "elektrikli araç", "akıllı telefon"),
    "bilim": ("bilim", "uzay", "teleskop", "evren", "fizik", "kimya", "biyoloji", "matematik", "iklim", "okyanus",
              "deprem", "yanardağ", "evrim", "genetik", "dna", "hücre", "mitokondri", "bakteri", "virüs", "beyin",
              "paleontolog", "fosil", "gezegen", "kasırga", "nükleer", "görelilik", "kuantum", "astronomi",
              "hayvan", "atom", "molekül"),
    "ekonomi": ("ekonomi", "makroekonomi", "enflasyon", "merkez bankası", "işsizlik", "istihdam", "büyüme",
                "finansal kriz", "dış ticaret", "ihracat", "ithalat", "para politikası", "maliye", "vergi",
                "reform", "kapitalizm", "orta vadeli program", "döviz", "fiyat endeksi", "fitch", "moody"),
    "finans": ("bileşik faiz", "finansal okuryazarlık", "fon", "birikim", "bütçe", "hisse", "borsa", "piyasa",
               "portföy", "getiri", "tasarruf", "yatırım", "yatırımcı", "ponzi", "tasfiye", "altın", "spk"),
    "kitap": ("kitap", "kitab", "roman", "öykü", "edebiyat", "yazar", "yazdı", "eseri", "eser", "şiir", "şair",
              "biyografi", "çeviri", "okudum", "nobel"),
    "yemek": ("yemek", "mutfak", "pişir", "tarif", "gastronomi", "biber", "fermantasyon", "lezzet", "hamur"),
    "spor": ("spor", "futbol", "basketbol", "koşu", "antrenman", "tenis", "falso", "voleybol", "olimpiyat",
             "yüzme", "bisiklet", "ralli", "formula 1", "grand prix", "jimnastik", "lig", "sezon", "maç",
             "milli takım", "hakem", "transfer", "şampiyon", "nba", "uefa", "boks", "güreş", "hentbol"),
}
# Başlıkta açıklayıcı / inceleyici içerik işareti.
QUALITY_TERMS = ("neden", "nasıl", "nedir", "nelerdir", "ne anlatır", "ne işe yarar", "rehber", "inceleme",
                 "üzerine", "analiz", "açıkl", "değerlendir", "eleştiri", "deneme", "tarihçe", "sırrı",
                 "kuralları", "mümkün mü", "gerçekten", "keşif", "sorunu", "çözüm", "sınırı", "etkisi",
                 "tarihi", "osmanlı", "geleneksel", "kültür")
# Önerilmeyecek türler: yatırım turu duyurusu, piyasa anlık fiyatı, reklam, magazin.
NEGATIVE_TERMS = ("çekiliş", "kupon kodu", "basın bülteni", "imza günü", "yatırım aldı", "değerleme",
                  "halka arz", "sponsorlu", "canlı yayın", "son durum", "güne yükseliş", "işçi alacak",
                  "işçi alımı", "ödemeleri", "hesaplara yatırıldı", "bilet satışı", "indirim", "kampanya",
                  "burç yorum", "burcu yorum", "burçlar", "astroloji", "fragman", "açılış gecesi", "kırmızı halı", "maç özeti", "reklam")
# Haberlerde öne çıkarılan önemli gelişmeler.
IMPORTANT_NEWS_TERMS = ("enflasyon", "işsizlik", "büyüme", "ihracat", "merkez bankası", "faiz", "fitch",
                        "moody", "fon", "cari açık", "rezerv", "şampiyon", "istifa", "veda", "yasağı",
                        "grand prix", "rekor", "madalya", "olimpiyat", "final")
DEVELOPMENT_TERMS = ("açıklandı", "açıkladı", "tanıttı", "duyurdu", "kullanıma sundu", "başlıyor", "başladı",
                     "yayımlandı", "kazandı", "şampiyon", "rekor", "zirve", "ilk kez", "istifa", "veda", "ödül",
                     "finalist", "yeni roman", "yeni kitap", "yapılacak", "erteledi")
# Zayıf içerik işaretleri (-2): yayınevi tanıtım metni, rutin röportaj ve duyuru.
WEAK_TERMS = ("yeni kitap", "günün önerisi", "sayısı yayımlandı", "özel röportaj")
CLICKBAIT_MARKS = ("\U0001F631", "\U0001F92F", "\U0001F60D", "\U0001F525", "\U0001F60E", "\U0001F4B8", "\U0001F90C", "#shorts")
TIER_BASE = {1: 2, 2: 4, 3: 6}
QUALITY_MIN = 5
# Rol çeşitliliği ancak bu puandaki adaylar için öncelik kazanır; zayıf bir
# "gelişme", güçlü bir yazının önüne geçmesin.
ROLE_PRIORITY_MIN = 7
NEWS_QUALITY_MIN = 4
DOMESTIC_TERMS = ("türkiye", "türk", "istanbul", "ankara", "erdoğan", "tbmm", "fon krizi")
# Terimler kelime başında aranır; Türkçe ekler serbesttir (roman → romanı).
# Aynı harflerle başlayıp başka anlama gelen kelimeler burada elenir.
FALSE_FRIENDS = {
    "fon": ("fonksiyon", "fonetik"),
    "getiri": ("getiril", "getirir", "getirip", "getirin", "getirince"),
    "tarif": ("tarife",),
    "roman": ("romanya", "romantik", "romantizm"),
    "koşu": ("koşul",),
    "hisse": ("hisset",),
    "yazar": ("yazarak",),
    "kombin": ("kombine",),
    "evren": ("evrensel",),
    "türk": ("türkçe",),
    "lig": ("ligh",),
    "maç": ("maça",),
    "eser": ("eserek",),
    "altın": ("altında",),
    "final": ("finale",),
}

def normalized(text):
    # str.lower() Türkçe I/İ çiftini bilmez: "IŞIK".lower() → "işik" olurdu.
    return text.replace("I", "ı").replace("İ", "i").lower().replace("â", "a").replace("î", "i").replace("û", "u")

def has_term(text, term):
    """Metinde terimle başlayan bir kelime var mı? (telefon ≠ fon, getirildi ≠ getiri)"""
    for match in re.finditer(r"(?<!\w)" + re.escape(term) + r"(\w*)", text):
        if not (term + match.group(1)).startswith(FALSE_FRIENDS.get(term, ())):
            return True
    return False

def has_any(text, terms):
    return any(has_term(text, term) for term in terms)

def _quality(item, title, profile, news=False):
    """Kural puanı (yaklaşık 0-12): kaynak seviyesi + başlıktaki olumlu/olumsuz işaretler."""
    score = 4 if news else TIER_BASE.get(profile.tier if profile else 2, 4)
    if news and has_any(title, IMPORTANT_NEWS_TERMS):
        score += 2
    if has_any(title, QUALITY_TERMS):
        score += 2
    if "?" in item.title:
        score += 1
    if len(item.description) >= 120:
        score += 1
    if any(mark in item.title.lower() for mark in CLICKBAIT_MARKS) or item.title.count("!") >= 2:
        score -= 1
    if has_any(normalized(item.title + " " + item.description[:200]), WEAK_TERMS):
        score -= 2
    return max(0, score)


def _role(item, title):
    if item.content_type == "video":
        return "video"
    if item.content_type == "news" or has_any(title, DEVELOPMENT_TERMS):
        return "gelisme"
    return "derinlik"


REASONS = {
    "gelisme": "Bu konudaki son gelişmelerden; güncelliği ve önemi nedeniyle seçildi.",
    "video": "Konuyu anlatan, kaynağı ve başlığı açıklayıcı içerik ölçütlerine uyan bir video.",
    "derinlik": "Bir konuyu açıklayan veya inceleyen yazı; kaynağı ve başlığı derinlemesine içerik ölçütlerine uyuyor.",
}


def prepare_candidate(item, profile=None):
    """Başlık, açıklama ve kaynak profilinden konu, rol ve kalite puanı çıkar.

    Kaynağın profili yalnızca ağırlık katar: içerikte konuya dair en az bir işaret
    olmadan (örn. kitap sitesindeki bir yemek yazısı) konu atanmaz."""
    title = normalized(item.title)
    text = normalized(item.title + " " + item.description)
    if has_any(title, NEGATIVE_TERMS):
        return None
    if item.content_type == "news" and item.topic not in TOPIC_TERMS:
        # Güncel haberler ayrı kurallarla seçilir: Türkiye/dünya dengesi ve önem puanı.
        topic, role, quality = "guncel", "gelisme", 0
        reason = "Türkiye ve dünya gündeminden; güncellik, haber konusu ve yayıncı çeşitliliğiyle seçildi."
    elif item.content_type == "news":
        # Konusu belli haber akışı (spor, ekonomi): o konunun "gelişme" adayı.
        topic, role = item.topic, "gelisme"
        quality = _quality(item, title, profile, news=True)
        if quality < NEWS_QUALITY_MIN:
            return None
        reason = REASONS["gelisme"]
    else:
        evidence = {topic: sum(3 if has_term(title, term) else 1 if has_term(text, term) else 0 for term in terms)
                    for topic, terms in TOPIC_TERMS.items()}
        preferred = profile.topics if profile else ()
        scores = {topic: value + (2 if topic in preferred else 0) for topic, value in evidence.items()}
        topic = max(scores, key=lambda name: (scores[name], name in preferred))
        if evidence[topic] < 1 or scores[topic] < 3:
            return None
        role = _role(item, title)
        # Başlığında konunun kendisi geçen içerik, yalnızca kaynağı nedeniyle eşleşenden önce gelir.
        quality = _quality(item, title, profile) + (1 if evidence[topic] >= 3 else 0)
        if quality < QUALITY_MIN:
            return None
        reason = REASONS[role]
    host = (urlsplit(item.url).hostname or "").removeprefix("www.")
    publisher = item.source_id if host in {"youtube.com", "youtu.be"} else host
    scope = item.news_scope
    if topic == "guncel" and not scope:
        scope = "turkiye" if has_any(title, DOMESTIC_TERMS) else "dunya"
    return replace(item, url=canonical_url(item.url), topic=topic, news_scope=scope,
                   publisher_id=publisher, purpose="current", recommendation_kind="timely",
                   recommendation_reason=reason, editorial_reviewed=False, role=role, quality=quality)

_INVALID = object()

def publication_day(item):
    """Türkiye saatine göre yayın günü; tarih yoksa None, bozuk/saat dilimsizse _INVALID."""
    raw_date = item.get("published_at")
    try:
        published = datetime.fromisoformat(raw_date) if raw_date else None
    except (ValueError, TypeError):
        return _INVALID
    if published is None:
        return None
    if published.tzinfo is None:
        return _INVALID
    return published.astimezone(TURKEY_TIME).date()

def age_limit(item):
    """Tarihli içeriğin kaç gün önerilebileceği; temel içerikte None."""
    if item["content_type"] == "news":
        return NEWS_MAX_AGE_DAYS.get(item["topic"])
    if item.get("recommendation_kind") == "foundation":
        return None
    limit = MAX_AGE_DAYS.get(item["topic"], 30)
    return min(limit, DEVELOPMENT_MAX_AGE_DAYS) if item.get("role") == "gelisme" else limit

def eligible(item, day):
    # Eski havuzdaki yalnızca kaynak etiketine dayanmış kayıtları kullanma.
    if not item.get("recommendation_reason") or not item.get("publisher_id"):
        return False
    published_day = publication_day(item)
    if published_day is _INVALID or (published_day and published_day > day):
        return False
    if item["content_type"] == "news":
        limit = age_limit(item)
        return limit is not None and published_day is not None and 0 <= (day-published_day).days <= limit
    if item.get("recommendation_kind") == "foundation":
        # 'Eski' veya 'blog' olmak zamansızlık kanıtı değildir.
        return item.get("editorial_reviewed") is True
    return item.get("recommendation_kind") == "timely" and published_day is not None and 0 <= (day-published_day).days <= age_limit(item)

def expired(item, day):
    """Bu gün ve sonrasında artık hiç önerilemeyecek havuz kaydı mı?

    Gelecek tarihli kayıt süresi dolmuş sayılmaz; günü gelince uygun olabilir."""
    if not item.get("recommendation_reason") or not item.get("publisher_id"):
        return True
    published_day = publication_day(item)
    if published_day is _INVALID:
        return True
    if item["content_type"] != "news":
        if item.get("recommendation_kind") == "foundation":
            return item.get("editorial_reviewed") is not True
        if item.get("recommendation_kind") != "timely":
            return True
    limit = age_limit(item)
    if limit is None or published_day is None:
        return True
    return (day - published_day).days > limit

def news_importance(item):
    """Şeffaf, basit konu puanı; editoryal önem kararı veren bir LLM değildir."""
    title = normalized(item["title"])
    terms = ("savaş", "ateşkes", "deprem", "seçim", "meclis", "yasama", "kriz", "zirve", "iklim", "afet", "merkez bankası", "enflasyon", "saldırı")
    return sum(has_term(title, term) for term in terms)


def normalize_news_scope(item):
    if item["topic"] != "guncel" or item.get("news_scope") in {"turkiye", "dunya"}:
        return item
    # Eski havuz kayıtları yeni alanı içermeyebilir.
    domestic = item.get("source_id") == "trt-guncel" or has_any(normalized(item["title"]), DOMESTIC_TERMS)
    return {**item, "news_scope": "turkiye" if domestic else "dunya"}


def select_items(candidates, day, retained=()):
    unique = {}
    for item in candidates:
        item = normalize_news_scope(item)
        if eligible(item, day):
            unique.setdefault(canonical_url(item["url"]), item)
    retained = [normalize_news_scope(item) for item in retained if eligible(item, day)]
    selected = []
    used = set()
    for topic in sorted({i["topic"] for i in (*unique.values(), *retained)}):
        limit = DAILY_TARGETS.get(topic, DEFAULT_DAILY_TARGET)
        picked = []
        for item in retained:
            key = canonical_url(item["url"])
            if item["topic"] == topic and key not in used and len(picked) < limit:
                picked.append(item)
                used.add(key)
        remaining = [i for key, i in unique.items() if i["topic"] == topic and key not in used]
        while remaining and len(picked) < limit:
            publishers = [i["publisher_id"] for i in picked]
            # Güncel'de bir yayıncı en fazla üç, diğerlerinde çeşitlilik öncelikli.
            options = [i for i in remaining if publishers.count(i["publisher_id"]) < 3] if topic == "guncel" else [i for i in remaining if i["publisher_id"] not in publishers]
            if not options and len(picked) < MIN_ITEMS_PER_TOPIC:
                options = remaining  # Asgari sayıyı tamamlamak için aynı yayıncıya izin verilir.
            if not options:
                break
            def rank(item):
                stamp = -(datetime.fromisoformat(item["published_at"]).timestamp() if item.get("published_at") else 0)
                if topic == "guncel":
                    return (sum(p.get("news_scope") == item.get("news_scope") for p in picked), publishers.count(item["publisher_id"]), -news_importance(item), stamp, item["url"])
                # Önce eksik rol (gelişme / video / derinlik), sonra yayıncı çeşitliliği ve kalite.
                return (quality_of(item) < ROLE_PRIORITY_MIN or any(role_of(p) == role_of(item) for p in picked),
                        item["publisher_id"] in publishers,
                        -quality_of(item),
                        any(p["content_type"] == item["content_type"] for p in picked),
                        stamp, item["url"])
            best = min(options, key=rank)
            picked.append(best)
            used.add(canonical_url(best["url"]))
            remaining = [i for i in remaining if canonical_url(i["url"]) not in used]
        selected.extend(picked)
    return selected


def role_of(item):
    """Eski kayıtlarda rol alanı yoktur; türünden çıkarılır."""
    if item.get("role"):
        return item["role"]
    return "video" if item["content_type"] == "video" else "gelisme" if item["content_type"] == "news" else "derinlik"


def quality_of(item):
    # Elle incelenmiş içerik kural puanından bağımsız olarak güçlü aday sayılır.
    return item.get("quality") or (8 if item.get("editorial_reviewed") else 5)


def topic_shortfalls(items, topics):
    return {topic: MIN_ITEMS_PER_TOPIC - sum(i["topic"] == topic for i in items)
            for topic in topics if sum(i["topic"] == topic for i in items) < MIN_ITEMS_PER_TOPIC}

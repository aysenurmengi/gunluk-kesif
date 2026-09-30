"""Tercih örneklerinden yazılmış açık kurallar. Öğrenilmiş bir AI modeli değil."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import re
from urllib.parse import urlsplit
from .content import canonical_url

POLICY_VERSION = 3
MIN_ITEMS_PER_TOPIC = 2
DAILY_TARGETS = {"guncel": 6, "spor": 3}
TURKEY_TIME = timezone(timedelta(hours=3))
# Model/haber/piyasa bilgisinin yaşlanma hızı farklıdır.
MAX_AGE_DAYS = {"teknoloji": 30, "ekonomi": 30, "finans": 7, "kitap": 60, "yemek": 60, "moda": 60, "spor": 30}
NEWS_MAX_AGE_DAYS = {"guncel": 3, "spor": 7}
TOPIC_TERMS = {
    "teknoloji": ("yapay zeka", "dil modeli", "gpt", "robot", "yazılım", "şehir", "teknoloji", "mühendis", "çip", "algoritma"),
    "ekonomi": ("ekonomi", "makroekonomi", "enflasyon", "merkez bankası", "işsizlik", "büyüme", "finansal kriz", "dış ticaret", "para politikası"),
    "finans": ("bileşik faiz", "finansal okuryazarlık", "fon", "birikim", "bütçe", "hisse", "borsa", "piyasa", "portföy", "getiri", "tasarruf", "yatırım"),
    "kitap": ("kitap", "roman", "öykü", "edebiyat", "yazar", "eseri"),
    "yemek": ("yemek", "mutfak", "pişir", "tarif", "gastronomi", "biber", "fermantasyon"),
    "moda": ("moda", "giyim", "gardırop", "gardirop", "kumaş", "kombin", "stil rehberi"),
    "spor": ("spor", "futbol", "basketbol", "koşu", "antrenman", "tenis", "falso", "voleybol", "olimpiyat", "yüzme", "bisiklet", "ralli", "formula 1", "jimnastik"),
}
EXPLANATION_TERMS = ("neden", "nasıl", "nedir", "rehber", "inceleme", "üzerine", "analiz", "açıkl", "değerlendir", "model", "kriz", "şehir", "piyasa", "borsa", "eleştiri", "deneme", "öykü", "ekonomi", "yatırım", "finans")
EXCLUDED_TERMS = ("çekiliş", "kupon kodu", "basın bülteni", "imza günü")
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
    "moda": ("modal",),
    "türk": ("türkçe",),
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

def prepare_candidate(item):
    """Başlık+akış açıklamasını süz. Kaynağın konu etiketi karar vermez."""
    title = normalized(item.title)
    text = normalized(item.title + " " + item.description)
    if has_any(title, EXCLUDED_TERMS):
        return None
    if item.content_type == "news":
        # Yalnızca açıkça spor olarak tanımlanmış akış spor gündemine gider.
        topic = "spor" if item.topic == "spor" else "guncel"
        reason = "Spor dünyasındaki güncel gelişmelerden seçildi." if topic == "spor" else "Türkiye ve dünya gündeminden; güncellik, haber konusu ve yayıncı çeşitliliğiyle seçildi."
    else:
        scores = {topic: sum(3 if has_term(title, term) else 1 if has_term(text, term) else 0 for term in terms)
                  for topic, terms in TOPIC_TERMS.items()}
        topic = max(scores, key=scores.get)
        if scores[topic] < 3 or not has_any(title, EXPLANATION_TERMS):
            return None
        reason = "Başlık ve kaynak açıklaması, seçtiğin konunun açıklama/inceleme ölçütleriyle eşleşti; güncellik filtresinden geçti."
    host = (urlsplit(item.url).hostname or "").removeprefix("www.")
    publisher = item.source_id if host in {"youtube.com", "youtu.be"} else host
    scope = item.news_scope
    if topic == "guncel" and not scope:
        scope = "turkiye" if has_any(title, DOMESTIC_TERMS) else "dunya"
    return replace(item, url=canonical_url(item.url), topic=topic, news_scope=scope,
                   publisher_id=publisher, purpose="current", recommendation_kind="timely",
                   recommendation_reason=reason, editorial_reviewed=False)

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
    return MAX_AGE_DAYS.get(item["topic"], 30)

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
        limit = DAILY_TARGETS.get(topic, MIN_ITEMS_PER_TOPIC)
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
                return (item["publisher_id"] in publishers,
                        topic == "spor" and any(p["content_type"] == "news" for p in picked) == (item["content_type"] == "news"),
                        not item.get("editorial_reviewed", False),
                        any(p["content_type"] == item["content_type"] for p in picked),
                        any(p.get("recommendation_kind") == item.get("recommendation_kind") for p in picked), stamp, item["url"])
            best = min(options, key=rank)
            picked.append(best)
            used.add(canonical_url(best["url"]))
            remaining = [i for i in remaining if canonical_url(i["url"]) not in used]
        selected.extend(picked)
    return selected


def topic_shortfalls(items, topics):
    return {topic: MIN_ITEMS_PER_TOPIC - sum(i["topic"] == topic for i in items)
            for topic in topics if sum(i["topic"] == topic for i in items) < MIN_ITEMS_PER_TOPIC}

"""Kaynak sözlüğünü ortak modele dönüştür ve URL tekrarlarını ayıkla."""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from ..models import ContentItem, Source


def parse_publication_date(value: str) -> datetime | None:
    """RSS tarihini UTC'ye çevir. Bilinmeyen tarihe bugünü atama."""
    if not value.strip():
        return None
    try:
        try:
            date = parsedate_to_datetime(value)
        except (ValueError, TypeError):
            date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        # Saat dilimi yoksa kaynağın yerel saatini tahmin etmiyoruz.
        if date.tzinfo is None:
            return None
        return date.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def normalize_article(article: dict[str, str], source: Source) -> ContentItem:
    return ContentItem(
        title=article["title"].strip(),
        url=article["link"].strip(),
        source_id=source.id,
        source_name=source.name,
        topic=source.topic,
        content_type=source.content_type,
        purpose=source.purpose,
        published_at=parse_publication_date(article.get("published_at", "")),
        description=article.get("description", ""),
        language=source.language, news_scope=source.news_scope,
    )


def remove_duplicates(items: list[ContentItem]) -> list[ContentItem]:
    """Aynı URL için ilk geleni tut; kaynak ve kayıt sırasını koru."""
    seen_urls = set()
    unique_items = []
    for item in items:
        if item.url in seen_urls:
            continue
        seen_urls.add(item.url)
        unique_items.append(item)
    return unique_items


def canonical_url(url):
    """YouTube paylaşım URL'lerini birleştir; yalnızca bilinen takip alanlarını at."""
    parts = urlsplit(url)
    host = (parts.hostname or "").removeprefix("www.")
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    video = parts.path.strip("/") if host == "youtu.be" else query.get("v") if host in {"youtube.com", "m.youtube.com"} else None
    if video:
        return "https://www.youtube.com/watch?" + urlencode({"v": video})
    pairs = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
             if not key.startswith("utm_") and key not in {"si", "feature", "at_medium", "at_campaign"}]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(pairs), ""))

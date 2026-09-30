"""Kaynakların ve içeriklerin ortak veri yapıları."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    feed_url: str
    topic: str
    content_type: str = "article"
    purpose: str = "current"
    language: str = "tr"
    news_scope: str = ""


@dataclass(frozen=True)
class ContentItem:
    title: str
    url: str
    source_id: str
    source_name: str
    topic: str
    content_type: str
    purpose: str
    published_at: datetime | None
    description: str = ""
    publisher_id: str = ""
    recommendation_reason: str = ""
    recommendation_kind: str = ""
    editorial_reviewed: bool = False
    publication_date_only: bool = False
    language: str = "tr"
    news_scope: str = ""
    # Konu içindeki yeri: gelisme (yeni gelişme), video, derinlik (açıklayıcı yazı).
    role: str = ""
    # Kural tabanlı kalite puanı (yaklaşık 0-12); aynı konudaki adayları sıralar.
    quality: int = 0


@dataclass(frozen=True)
class SourceProfile:
    """Bir akışın hangi konulara yakın olduğu ve genel kalite seviyesi (1-3).

    Konu yine içerik düzeyinde belirlenir; profil yalnızca ağırlık katar.
    """
    topics: tuple[str, ...] = ()
    tier: int = 2

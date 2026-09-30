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

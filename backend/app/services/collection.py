"""Seçilen kaynakları oku; dönüştür, birleştir ve tekrarları çıkar."""

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

from ..models import ContentItem, Source
from ..sources.rss import RssError, download_rss, parse_rss
from .content import normalize_article, remove_duplicates


@dataclass
class CollectionResult:
    items: list[ContentItem]
    source_counts: dict[str, int]
    errors: dict[str, str]
    duplicate_count: int


def collect_contents(sources: list[Source]) -> CollectionResult:
    all_items = []
    source_counts = {}
    errors = {}
    def read(source):
        try:
            return parse_rss(download_rss(source.feed_url)), None
        except RssError as error:
            return [], str(error)

    # Ağ beklemelerini paylaş; sonuçları katalog sırasıyla birleştir.
    with ThreadPoolExecutor(max_workers=4) as executor:
        for source, (articles, error) in zip(sources, executor.map(read, sources)):
            if error is not None:
                errors[source.id] = error
                continue
            source_counts[source.id] = len(articles)
            all_items.extend(normalize_article(article, source) for article in articles)

    unique_items = remove_duplicates(all_items)
    return CollectionResult(
        items=unique_items,
        source_counts=source_counts,
        errors=errors,
        duplicate_count=len(all_items) - len(unique_items),
    )

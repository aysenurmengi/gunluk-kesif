"""Günlük seçki, tercih politikası ve kalıcı arşiv iş akışı."""
from dataclasses import asdict, fields
from datetime import datetime, timezone, timedelta
import logging
import threading
from ..config import running_on_vercel
from ..models import ContentItem
from ..repositories import daily as repository, database
from ..sources.daily_catalog import FEED_SOURCES, CURATED_SOURCES, SOURCE_PROFILES, SUPPORTED_TOPICS, CATALOG_REVISION, curated_items
from .collection import collect_contents
from .content import canonical_url
from .recommendation_policy import POLICY_VERSION, TURKEY_TIME, expired, prepare_candidate, select_items, topic_shortfalls

logger = logging.getLogger(__name__)
RETRY_SHORTFALL_AFTER = timedelta(minutes=15)
CONTENT_FIELDS = {field.name for field in fields(ContentItem)}

def today():
    return datetime.now(TURKEY_TIME).date()

class CollectionUnavailable(Exception):
    pass

def serialize(item):
    result = asdict(item)
    result["published_at"] = item.published_at.isoformat() if item.published_at else None
    result["url"] = canonical_url(item.url)
    return result

def reevaluate(payload):
    """Havuzdaki otomatik adayı güncel kurallarla yeniden süz; elle incelenmişi koru."""
    if payload.get("editorial_reviewed") is True:
        return payload
    try:
        published = datetime.fromisoformat(payload["published_at"]) if payload.get("published_at") else None
        item = ContentItem(**{key: value for key, value in payload.items() if key in CONTENT_FIELDS}
                           | {"published_at": published})
    except (TypeError, ValueError):
        return None
    prepared = prepare_candidate(item, SOURCE_PROFILES.get(item.source_id))
    return serialize(prepared) if prepared else None

def freshness(existing, day):
    """'fresh': olduğu gibi kullan, 'stale': eksikler için yeniden dene, 'missing': oluştur."""
    if existing is None:
        return "missing"
    if day != today():
        return "fresh"
    if existing.get("policy_version") != POLICY_VERSION or existing.get("catalog_revision") != CATALOG_REVISION:
        return "missing"
    if not existing.get("topic_shortfalls"):
        return "fresh"
    try:
        generated = datetime.fromisoformat(existing["generated_at"])
        return "fresh" if datetime.now(timezone.utc) - generated < RETRY_SHORTFALL_AFTER else "stale"
    except (ValueError, KeyError, TypeError):
        return "missing"

def get_daily(day, db_path=None, wait_for_refresh=True):
    """Kayıtlı seçkiyi döndür; bugün için gerekirse kaynakları okuyup oluştur.

    Eksik konulu seçki 15 dakika sonra yeniden tamamlanır. wait_for_refresh=False
    ise kullanıcı mevcut kartları hemen görür, tamamlama arka planda yapılır.
    Vercel'de yanıt sonrası iş parçacığı durdurulur; orada tamamlamayı cron yapar."""
    target = database.DATABASE if db_path is None else db_path
    with repository.connect(target) as db:
        existing = repository.read_edition(db, day.isoformat())
    if day != today():
        return existing
    state = freshness(existing, day)
    if state == "fresh":
        return existing
    if state == "stale" and not wait_for_refresh:
        if not running_on_vercel():
            refresh_in_background(day, target)
        return existing
    return build_edition(day, target)

_refreshing = set()
_refreshing_lock = threading.Lock()

def refresh_in_background(day, target):
    key = (str(target), day)
    with _refreshing_lock:
        if key in _refreshing:
            return
        _refreshing.add(key)

    def run():
        try:
            build_edition(day, target)
        except Exception:
            logger.exception("Günlük seçki arka planda tamamlanamadı (%s)", day)
        finally:
            with _refreshing_lock:
                _refreshing.discard(key)

    threading.Thread(target=run, name=f"daily-refresh-{day}", daemon=True).start()

def build_edition(day, target):
    result = collect_contents(list(FEED_SOURCES))
    accepted = [candidate for item in result.items
                if (candidate := prepare_candidate(item, SOURCE_PROFILES.get(item.source_id))) is not None]
    # Referansın editoryal bilgileri aynı URL'nin ham RSS kaydı tarafından ezilmesin.
    items = accepted + curated_items()
    with repository.connect(target) as db:
        repository.lock_editions(db)
        existing = repository.read_edition(db, day.isoformat())
        if freshness(existing, day) == "fresh":
            return existing
        repository.store_candidates(db, [serialize(item) for item in items])
        seen = {canonical_url(url) for url in repository.recommended_urls(db)}
        candidates, dead = [], []
        for payload in repository.unused_candidates(db):
            current = reevaluate(payload)
            # Kaldırılan konudaki (örn. moda) eski adaylar da bir daha önerilmez.
            if (current is None or current["topic"] not in SUPPORTED_TOPICS or expired(current, day)
                    or canonical_url(current["url"]) in seen):
                dead.append(payload["url"])
            else:
                candidates.append(current)
        # Bir daha önerilemeyecek adaylar havuzu büyütmesin.
        repository.delete_candidates(db, dead)
        # Katalog büyürken bugünün geçerli kartlarını tut, boş yerleri tamamla.
        retained = [item for item in (existing["items"] if existing and existing.get("policy_version", 0) >= 2 else [])
                    if item["topic"] in SUPPORTED_TOPICS]
        # Yeni katalogdaki konu düzeltmelerini yalnızca bugünün kartlarına uygula.
        reviewed = {canonical_url(item.url): serialize(item) for item in curated_items()}
        retained = [reviewed.get(canonical_url(item["url"]), item) for item in retained]
        retained = [{**item, "news_scope": "turkiye"} if item["topic"] == "guncel" and item.get("source_id") == "trt-guncel" else item for item in retained]
        chosen = select_items(candidates, day, retained=retained)
        payload = {
            "date": day.isoformat(), "items": chosen,
            "sources": [asdict(source) for source in (*CURATED_SOURCES, *FEED_SOURCES)],
            "supported_topics": list(SUPPORTED_TOPICS),
            "errors": result.errors, "policy_version": POLICY_VERSION, "catalog_revision": CATALOG_REVISION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "topic_shortfalls": topic_shortfalls(chosen, SUPPORTED_TOPICS),
        }
        if not chosen and result.errors:
            raise CollectionUnavailable("Kaynaklar okunamadı ve havuzda yeni uygun içerik yok. Yeniden deneyebilirsin.")
        # Eski politikanın bugünkü seçkisi bir kez yenilenir. Geçmiş günler ve
        # daha önce önerilen URL'lerin geçmişi korunur.
        repository.save_edition(db, payload)
        return payload

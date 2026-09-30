"""Aday havuzu, değişmeyen günlük seçki ve önerilen URL geçmişi."""
from .database import DB_PATH, connect, describe, dump_json, is_postgres, load_json

__all__ = ["DB_PATH", "connect", "describe", "is_postgres"]
# Aynı günün seçkisini iki isteğin aynı anda oluşturmasını önleyen PostgreSQL kilidi.
EDITION_LOCK_ID = 7_302_026


def lock_editions(db):
    """Günlük seçki oluşturulurken diğer yazıcıları beklet (işlem sonunda açılır)."""
    if db.postgres:
        db.execute("SELECT pg_advisory_xact_lock(?)", (EDITION_LOCK_ID,))
    else:
        db.execute("BEGIN IMMEDIATE")


def read_edition(db, day):
    row = db.execute("SELECT payload FROM editions WHERE day = ?", (db.day(day),)).fetchone()
    return load_json(row[0]) if row else None


def list_dates(db):
    return [str(row[0]) for row in db.execute("SELECT day FROM editions ORDER BY day DESC")]


def store_candidates(db, items):
    db.executemany(f"INSERT INTO pool VALUES (?, {db.json_param}) ON CONFLICT(url) DO UPDATE SET payload=excluded.payload",
                   [(item["url"], dump_json(item)) for item in items])


def unused_candidates(db):
    return [load_json(row[0]) for row in db.execute(
        "SELECT payload FROM pool p WHERE NOT EXISTS (SELECT 1 FROM recommendations r WHERE r.url = p.url)")]


def delete_candidates(db, urls):
    db.executemany("DELETE FROM pool WHERE url = ?", [(url,) for url in urls])


def save_edition(db, payload):
    day = db.day(payload["date"])
    db.execute(f"INSERT INTO editions VALUES (?, {db.json_param}) ON CONFLICT(day) DO UPDATE SET payload=excluded.payload",
               (day, dump_json(payload)))
    # Bir URL bir kez gösterildiyse, gün yeniden üretilse bile görülmüş sayılır.
    db.executemany("INSERT INTO recommendations VALUES (?, ?) ON CONFLICT(url) DO NOTHING",
                   [(item["url"], day) for item in payload["items"]])


def recommended_urls(db):
    return [row[0] for row in db.execute("SELECT url FROM recommendations")]

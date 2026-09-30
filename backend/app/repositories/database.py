"""Veritabanı bağlantısı ve şema: PostgreSQL veya SQLite.

DATABASE_URL (postgresql://...) tanımlıysa PostgreSQL, değilse data/ altındaki
SQLite dosyası kullanılır. İki sürücünün farkları bu dosyada tutulur.
"""
from datetime import date, datetime
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from ..config import PROJECT_ROOT, load_env

load_env()
DB_PATH = PROJECT_ROOT / "data" / "discovery.sqlite3"
DATABASE = os.environ.get("DATABASE_URL") or DB_PATH
SCHEMA_LOCK_ID = 7_302_027

SQLITE_SCHEMA = """
    PRAGMA foreign_keys = ON;
    CREATE TABLE IF NOT EXISTS pool (url TEXT PRIMARY KEY, payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS editions (day TEXT PRIMARY KEY, payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS recommendations (
        url TEXT PRIMARY KEY, day TEXT NOT NULL REFERENCES editions(day));
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS sessions (
        token_hash TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS saved_items (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        url TEXT NOT NULL, payload TEXT NOT NULL, saved_at TEXT NOT NULL,
        PRIMARY KEY (user_id, url));
"""
POSTGRES_SCHEMA = """
    CREATE TABLE IF NOT EXISTS pool (url TEXT PRIMARY KEY, payload JSONB NOT NULL);
    CREATE TABLE IF NOT EXISTS editions (day DATE PRIMARY KEY, payload JSONB NOT NULL);
    CREATE TABLE IF NOT EXISTS recommendations (
        url TEXT PRIMARY KEY, day DATE NOT NULL REFERENCES editions(day));
    CREATE INDEX IF NOT EXISTS recommendations_day_idx ON recommendations (day);
    CREATE TABLE IF NOT EXISTS users (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL);
    CREATE TABLE IF NOT EXISTS sessions (
        token_hash TEXT PRIMARY KEY,
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires_at TIMESTAMPTZ NOT NULL);
    CREATE INDEX IF NOT EXISTS sessions_user_idx ON sessions (user_id);
    CREATE TABLE IF NOT EXISTS saved_items (
        user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        url TEXT NOT NULL, payload JSONB NOT NULL, saved_at TIMESTAMPTZ NOT NULL,
        PRIMARY KEY (user_id, url));
"""
_postgres_ready = set()
_postgres_ready_lock = threading.Lock()


def is_postgres(target):
    return isinstance(target, str) and target.startswith(("postgresql://", "postgres://"))


def describe(target):
    """Günlüklerde parolayı göstermeden hedef veritabanını anlat."""
    if not is_postgres(target):
        return f"SQLite ({target})"
    from psycopg.conninfo import conninfo_to_dict
    info = conninfo_to_dict(target)
    return f"PostgreSQL ({info.get('user', '?')}@{info.get('host', 'localhost')}:{info.get('port', 5432)}/{info.get('dbname', '?')})"


class Database:
    """sqlite3 ve psycopg bağlantılarını aynı küçük arayüzle kullan."""

    def __init__(self, connection, postgres):
        self.connection = connection
        self.postgres = postgres
        # JSON SQLite'ta metin, PostgreSQL'de JSONB olarak saklanır.
        self.json_param = "CAST(? AS jsonb)" if postgres else "?"

    def _sql(self, sql):
        return sql.replace("?", "%s") if self.postgres else sql

    def execute(self, sql, params=()):
        return self.connection.execute(self._sql(sql), params)

    def executemany(self, sql, rows):
        if not rows:
            return
        if self.postgres:
            with self.connection.cursor() as cursor:
                cursor.executemany(self._sql(sql), rows)
        else:
            self.connection.executemany(sql, rows)

    def day(self, value):
        return date.fromisoformat(value) if self.postgres else value

    def timestamp(self, value: datetime):
        # SQLite'ta aynı biçimli UTC metinleri sıralanabilir kalır.
        return value if self.postgres else value.isoformat(timespec="microseconds")


def load_json(value):
    return json.loads(value) if isinstance(value, str) else value


def dump_json(value):
    return json.dumps(value, ensure_ascii=False)


@contextmanager
def connect(target=None):
    target = DATABASE if target is None else target
    if is_postgres(target):
        import psycopg
        connection = psycopg.connect(target, connect_timeout=10)
        db = Database(connection, postgres=True)
        try:
            _ensure_postgres_schema(target, db)
        except Exception:
            connection.close()
            raise
    else:
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(target, timeout=30)
        db = Database(connection, postgres=False)
        try:
            connection.executescript(SQLITE_SCHEMA)
        except Exception:
            connection.close()
            raise
    try:
        yield db
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _ensure_postgres_schema(target, db):
    # Şema her süreçte bir kez kurulur; eşzamanlı CREATE yarışını kilit önler.
    with _postgres_ready_lock:
        if target in _postgres_ready:
            return
        db.execute("SELECT pg_advisory_xact_lock(?)", (SCHEMA_LOCK_ID,))
        for statement in filter(str.strip, POSTGRES_SCHEMA.split(";")):
            db.execute(statement)
        db.connection.commit()
        _postgres_ready.add(target)

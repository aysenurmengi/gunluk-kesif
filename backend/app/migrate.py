"""SQLite arşivini DATABASE_URL ile tanımlı PostgreSQL veritabanına kopyala.

Tekrar çalıştırılabilir: aynı gün ve URL'ler üzerine yazılır, önerilmiş URL
geçmişi korunur. Kullanıcılar e-postayla eşleştirilir; oturumlar taşınmaz,
yeniden giriş yapmak gerekir. SQLite dosyası değiştirilmez veya silinmez.

    .\\.venv\\Scripts\\python.exe -m backend.app.migrate
"""
import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .repositories import daily as repository, database, users


def main() -> int:
    parser = argparse.ArgumentParser(description="SQLite arşivini PostgreSQL'e kopyala.")
    parser.add_argument("--sqlite", type=Path, default=database.DB_PATH, help="Kaynak SQLite dosyası")
    parser.add_argument("--target", default=database.DATABASE, help="Hedef (varsayılan: DATABASE_URL)")
    args = parser.parse_args()
    if not database.is_postgres(args.target):
        parser.error("Hedef bir PostgreSQL adresi olmalı. .env dosyasına DATABASE_URL=postgresql://... yaz.")
    if not args.sqlite.exists():
        parser.error(f"SQLite dosyası bulunamadı: {args.sqlite}")

    source = sqlite3.connect(f"file:{args.sqlite.as_posix()}?mode=ro", uri=True)
    try:
        tables = {name for (name,) in source.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        rows = lambda table, sql: source.execute(sql).fetchall() if table in tables else []
        editions = [json.loads(payload) for (payload,) in rows("editions", "SELECT payload FROM editions ORDER BY day")]
        recommendations = rows("recommendations", "SELECT url, day FROM recommendations")
        pool = [json.loads(payload) for (payload,) in rows("pool", "SELECT payload FROM pool")]
        # Hesaplar eklenmeden önceki SQLite dosyalarında bu tablolar yoktur.
        accounts = rows("users", "SELECT id, email, password_hash, created_at FROM users")
        saved = rows("saved_items", "SELECT user_id, payload, saved_at FROM saved_items")
    finally:
        source.close()

    with database.connect(args.target) as db:
        repository.lock_editions(db)
        for edition in editions:
            repository.save_edition(db, edition)
        # Gösterilip sonra listeden düşen URL'ler de "görüldü" olarak taşınır.
        db.executemany("INSERT INTO recommendations VALUES (?, ?) ON CONFLICT(url) DO NOTHING",
                       [(url, db.day(day)) for url, day in recommendations])
        repository.store_candidates(db, pool)
        new_ids = {}
        for old_id, email, password_hash, created_at in accounts:
            created = datetime.fromisoformat(created_at)
            new_ids[old_id] = (users.create_user(db, email, password_hash, created)
                               or users.find_user_by_email(db, email)["id"])
        for user_id, payload, saved_at in saved:
            users.save_item(db, new_ids[user_id], json.loads(payload), datetime.fromisoformat(saved_at))
        counts = {table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                  for table in ("editions", "recommendations", "pool", "users", "saved_items")}

    print(f"Kaynak: {database.describe(args.sqlite)}")
    print(f"Hedef:  {database.describe(args.target)}")
    print(f"Taşınan: {len(editions)} gün, {len(recommendations)} önerilmiş URL, {len(pool)} aday, "
          f"{len(accounts)} kullanıcı, {len(saved)} kayıtlı içerik")
    print("Hedefteki toplam: " + ", ".join(f"{table} {count}" for table, count in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

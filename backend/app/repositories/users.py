"""Kullanıcılar, oturumlar ve kullanıcıya özel kaydedilen içerikler."""
from .database import dump_json, load_json


def create_user(db, email, password_hash, now):
    """Yeni kullanıcının kimliğini döndür; e-posta kayıtlıysa None."""
    row = db.execute(
        "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?) "
        "ON CONFLICT(email) DO NOTHING RETURNING id",
        (email, password_hash, db.timestamp(now))).fetchone()
    return row[0] if row else None


def find_user_by_email(db, email):
    row = db.execute("SELECT id, email, password_hash FROM users WHERE email = ?", (email,)).fetchone()
    return {"id": row[0], "email": row[1], "password_hash": row[2]} if row else None


def create_session(db, token_hash, user_id, expires_at):
    db.execute("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
               (token_hash, user_id, db.timestamp(expires_at)))


def find_session_user(db, token_hash, now):
    row = db.execute(
        "SELECT u.id, u.email FROM sessions s JOIN users u ON u.id = s.user_id "
        "WHERE s.token_hash = ? AND s.expires_at > ?", (token_hash, db.timestamp(now))).fetchone()
    return {"id": row[0], "email": row[1]} if row else None


def delete_session(db, token_hash):
    db.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))


def delete_expired_sessions(db, now):
    db.execute("DELETE FROM sessions WHERE expires_at <= ?", (db.timestamp(now),))


def list_saved(db, user_id):
    return [load_json(row[0]) for row in db.execute(
        "SELECT payload FROM saved_items WHERE user_id = ? ORDER BY saved_at DESC, url", (user_id,))]


def save_item(db, user_id, payload, now):
    # Aynı içerik yeniden kaydedilirse ilk kaydetme zamanı korunur.
    db.execute(
        f"INSERT INTO saved_items (user_id, url, payload, saved_at) VALUES (?, ?, {db.json_param}, ?) "
        "ON CONFLICT(user_id, url) DO UPDATE SET payload = excluded.payload",
        (user_id, payload["url"], dump_json(payload), db.timestamp(now)))


def remove_item(db, user_id, url):
    db.execute("DELETE FROM saved_items WHERE user_id = ? AND url = ?", (user_id, url))


def update_password_hash(db, user_id, password_hash):
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))

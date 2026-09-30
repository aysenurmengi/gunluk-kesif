"""Hesap açma, giriş ve oturumlar. Parolalar scrypt ile özetlenir, düz saklanmaz."""
from base64 import b64decode, b64encode
from collections import defaultdict, deque
from dataclasses import fields
from functools import cache
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets
import threading
from time import monotonic
from urllib.parse import urlsplit

from ..models import ContentItem
from ..repositories import database, users

SESSION_COOKIE = "gk_session"
SESSION_LIFETIME = timedelta(days=30)
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 256
MAX_SAVED_PAYLOAD_BYTES = 20_000
# OWASP'ın scrypt için önerdiği asgari değerler; bir özet ~0,5 sn ve 128 MiB bellek ister.
# Böylece veritabanı çalınsa bile parolaları deneme-yanılmayla bulmak çok pahalıdır.
SCRYPT = {"n": 2**17, "r": 8, "p": 1}
SCRYPT_MAXMEM = 256 * 1024 * 1024
LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 15 * 60
REGISTER_ATTEMPTS = 10
REGISTER_WINDOW_SECONDS = 60 * 60
CONTENT_FIELDS = {field.name for field in fields(ContentItem)}
# Sızıntı listelerinde en sık görülen parolalardan kısa bir örnek; tam liste değildir.
COMMON_PASSWORDS = {
    "12345678", "123456789", "1234567890", "12341234", "11111111", "00000000", "87654321",
    "password", "password1", "password123", "passw0rd", "qwerty123", "qwertyuiop", "asdfghjk",
    "iloveyou", "abcd1234", "abc12345", "parola123", "parola1234", "sifre123", "şifre123",
    "sifre1234", "şifre1234", "galatasaray", "fenerbahce", "fenerbahçe", "besiktas", "beşiktaş",
    "trabzonspor", "istanbul", "ankara06", "türkiye", "turkiye1", "12qwaszx", "1q2w3e4r", "1qaz2wsx",
}


class AuthError(Exception):
    """Kullanıcıya gösterilebilecek Türkçe mesaj ve HTTP durum kodu."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def now():
    return datetime.now(timezone.utc)


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=64, maxmem=SCRYPT_MAXMEM, **SCRYPT)
    return f"scrypt${SCRYPT['n']}${SCRYPT['r']}${SCRYPT['p']}${b64encode(salt).decode()}${b64encode(digest).decode()}"


def verify_password(password, stored):
    try:
        _, n, r, p, salt, digest = stored.split("$")
        expected = b64decode(digest)
        actual = hashlib.scrypt(password.encode(), salt=b64decode(salt), dklen=len(expected),
                                n=int(n), r=int(r), p=int(p), maxmem=SCRYPT_MAXMEM)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def needs_rehash(stored):
    """Eski/zayıf ayarlarla özetlenmiş parola girişte yeni ayarlarla yeniden özetlenir."""
    return not stored.startswith(f"scrypt${SCRYPT['n']}${SCRYPT['r']}${SCRYPT['p']}$")


@cache
def _dummy_hash():
    # Olmayan e-postada da aynı süre harcansın; yanıt süresi hesabın varlığını ele vermesin.
    return hash_password(secrets.token_urlsafe(16))


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def normalize_email(email):
    email = (email or "").strip().lower()
    local, _, domain = email.partition("@")
    if not local or "." not in domain or len(email) > 254 or any(c.isspace() for c in email):
        raise AuthError("Geçerli bir e-posta adresi yaz.")
    return email


def check_password(password, email=""):
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise AuthError(f"Parola en az {MIN_PASSWORD_LENGTH} karakter olmalı.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise AuthError("Parola çok uzun.")
    lowered = password.lower()
    if lowered in COMMON_PASSWORDS or len(set(lowered)) <= 2:
        raise AuthError("Bu parola çok yaygın veya tahmin edilmesi kolay. Başka bir parola seç.")
    name = email.partition("@")[0]
    if len(name) >= 3 and name in lowered:
        raise AuthError("Parola e-posta adresinin bir parçasını içermemeli.")


class AttemptLimiter:
    """Aynı anahtar için art arda denemeleri yavaşlat (bellekte tutulur)."""

    def __init__(self, attempts=LOGIN_ATTEMPTS, window=LOGIN_WINDOW_SECONDS,
                 message="Çok fazla hatalı deneme. 15 dakika sonra yeniden dene."):
        self.attempts, self.window, self.message = attempts, window, message
        self.events = defaultdict(deque)
        self.lock = threading.Lock()

    def _recent(self, key):
        queue = self.events[key]
        while queue and monotonic() - queue[0] > self.window:
            queue.popleft()
        return queue

    def check(self, key):
        with self.lock:
            if len(self._recent(key)) >= self.attempts:
                raise AuthError(self.message, 429)

    def record(self, key):
        with self.lock:
            self._recent(key).append(monotonic())

    def reset(self, key):
        with self.lock:
            self.events.pop(key, None)


login_limiter = AttemptLimiter()
# Aynı adresten toplu hesap açmayı yavaşlatır.
register_limiter = AttemptLimiter(REGISTER_ATTEMPTS, REGISTER_WINDOW_SECONDS,
                                "Bu cihazdan çok fazla hesap açıldı. Bir saat sonra yeniden dene.")


def _start_session(db, user_id):
    token = secrets.token_urlsafe(32)
    users.delete_expired_sessions(db, now())
    users.create_session(db, token_hash(token), user_id, now() + SESSION_LIFETIME)
    return token


def register(email, password, client="", target=None):
    email = normalize_email(email)
    check_password(password, email)
    register_limiter.check(client)
    with database.connect(target) as db:
        user_id = users.create_user(db, email, hash_password(password), now())
        if user_id is None:
            raise AuthError("Bu e-posta ile bir hesap zaten var. Giriş yapmayı dene.", 409)
        register_limiter.record(client)
        return {"id": user_id, "email": email}, _start_session(db, user_id)


def login(email, password, client="", target=None):
    email = (email or "").strip().lower()
    key = (client, email)
    login_limiter.check(key)
    with database.connect(target) as db:
        user = users.find_user_by_email(db, email)
        valid = verify_password(password or "", user["password_hash"] if user else _dummy_hash())
        if not user or not valid:
            login_limiter.record(key)
            raise AuthError("E-posta veya parola hatalı.", 401)
        login_limiter.reset(key)
        if needs_rehash(user["password_hash"]):
            users.update_password_hash(db, user["id"], hash_password(password))
        return {"id": user["id"], "email": user["email"]}, _start_session(db, user["id"])


def logout(token, target=None):
    if token:
        with database.connect(target) as db:
            users.delete_session(db, token_hash(token))


def session_user(token, target=None):
    if not token:
        return None
    with database.connect(target) as db:
        return users.find_session_user(db, token_hash(token), now())


def clean_saved_item(item):
    """Tarayıcıdan gelen kaydı içerik modelinin alanlarıyla sınırla ve bağlantıyı denetle."""
    if not isinstance(item, dict):
        raise AuthError("Kaydedilecek içerik geçersiz.")
    title, url = item.get("title"), item.get("url")
    if not isinstance(title, str) or not title.strip() or len(title) > 500:
        raise AuthError("Kaydedilecek içeriğin başlığı geçersiz.")
    parts = urlsplit(url) if isinstance(url, str) and len(url) <= 2048 else None
    if not parts or parts.scheme not in {"http", "https"} or not parts.netloc:
        raise AuthError("Kaydedilecek içeriğin bağlantısı geçersiz.")
    payload = {key: value for key, value in item.items() if key in CONTENT_FIELDS}
    if len(database.dump_json(payload).encode()) > MAX_SAVED_PAYLOAD_BYTES:
        raise AuthError("Kaydedilecek içerik çok büyük.")
    return payload


def list_saved(user, target=None):
    with database.connect(target) as db:
        return users.list_saved(db, user["id"])


def save(user, items, target=None):
    """Geçerli içerikleri kaydet; kaç tanesinin atlandığını döndür."""
    cleaned, skipped = [], 0
    for item in items:
        try:
            cleaned.append(clean_saved_item(item))
        except AuthError:
            skipped += 1
    with database.connect(target) as db:
        for payload in cleaned:
            users.save_item(db, user["id"], payload, now())
    return skipped


def remove(user, url, target=None):
    with database.connect(target) as db:
        users.remove_item(db, user["id"], url)

"""Hesaplar, oturum çerezi ve kullanıcıya özel kaydedilenler; geçici veritabanı."""
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.repositories import database
from backend.app.services import auth

ITEM = {"title": "Bir ekonomi yazısı", "url": "https://example.com/a", "topic": "ekonomi",
        "content_type": "article", "source_name": "Örnek", "extra_field": "atılır"}
PASSWORD = "gizli-parola-1"


class AuthTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "auth.sqlite3"
        self.use_database()
        patch.object(auth, "login_limiter", auth.AttemptLimiter()).start()
        patch.object(auth, "register_limiter", auth.AttemptLimiter(auth.REGISTER_ATTEMPTS, auth.REGISTER_WINDOW_SECONDS)).start()
        self.addCleanup(patch.stopall)
        self.client = self.new_client()

    def use_database(self):
        patch.object(database, "DATABASE", self.db).start()

    def new_client(self):
        client = TestClient(app)
        self.addCleanup(client.close)
        return client

    def register(self, client=None, email="okur@example.com"):
        return (client or self.client).post("/api/auth/register", json={"email": email, "password": PASSWORD})

    def test_saved_items_require_login(self):
        self.assertEqual(self.client.get("/api/auth/me").json(), {"user": None})
        for method, path in [("get", "/api/saved"), ("put", "/api/saved"), ("delete", "/api/saved?url=x")]:
            with self.subTest(path=path, method=method):
                response = getattr(self.client, method)(path, **({"json": {"item": ITEM}} if method == "put" else {}))
                self.assertEqual(response.status_code, 401)
                self.assertIn("giriş", response.json()["detail"]["message"])

    def test_register_sets_http_only_session_and_hashes_password(self):
        response = self.register(email="  Okur@Example.com ")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["user"]["email"], "okur@example.com")
        cookie = response.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=lax", cookie)
        self.assertEqual(self.client.get("/api/auth/me").json()["user"]["email"], "okur@example.com")
        with database.connect(self.db) as db:
            stored = db.execute("SELECT password_hash FROM users").fetchone()[0]
            token_hashes = [row[0] for row in db.execute("SELECT token_hash FROM sessions")]
        self.assertTrue(stored.startswith("scrypt$"))
        self.assertNotIn(PASSWORD, stored)
        self.assertNotIn(self.client.cookies[auth.SESSION_COOKIE], token_hashes)

    def test_register_validation_and_duplicates(self):
        self.assertEqual(self.client.post("/api/auth/register", json={"email": "yanlis", "password": PASSWORD}).status_code, 400)
        short = self.client.post("/api/auth/register", json={"email": "a@example.com", "password": "kisa"})
        self.assertEqual(short.status_code, 400)
        self.assertIn("8", short.json()["detail"]["message"])
        self.register()
        duplicate = self.register(self.new_client(), email="OKUR@example.com")
        self.assertEqual(duplicate.status_code, 409)

    def test_login_logout_and_generic_failure(self):
        self.register()
        other = self.new_client()
        wrong = other.post("/api/auth/login", json={"email": "okur@example.com", "password": "yanlis-parola"})
        unknown = other.post("/api/auth/login", json={"email": "yok@example.com", "password": PASSWORD})
        self.assertEqual((wrong.status_code, unknown.status_code), (401, 401))
        self.assertEqual(wrong.json(), unknown.json())
        self.assertEqual(other.post("/api/auth/login", json={"email": "OKUR@example.com", "password": PASSWORD}).status_code, 200)
        self.assertEqual(other.get("/api/auth/me").status_code, 200)
        self.assertEqual(other.post("/api/auth/logout").status_code, 204)
        self.assertIsNone(other.get("/api/auth/me").json()["user"])
        # Diğer cihazdaki oturum etkilenmez.
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)

    def test_repeated_failures_are_rate_limited(self):
        self.register()
        other = self.new_client()
        for _ in range(auth.LOGIN_ATTEMPTS):
            other.post("/api/auth/login", json={"email": "okur@example.com", "password": "yanlis-parola"})
        blocked = other.post("/api/auth/login", json={"email": "okur@example.com", "password": PASSWORD})
        self.assertEqual(blocked.status_code, 429)

    def test_expired_session_is_rejected(self):
        self.register()
        with patch.object(auth, "now", return_value=auth.now() + auth.SESSION_LIFETIME + timedelta(minutes=1)):
            self.assertIsNone(self.client.get("/api/auth/me").json()["user"])
            self.assertEqual(self.client.get("/api/saved").status_code, 401)

    def test_save_list_remove_and_users_are_isolated(self):
        self.register()
        saved = self.client.put("/api/saved", json={"item": ITEM})
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["items"], [{k: v for k, v in ITEM.items() if k != "extra_field"}])
        self.client.put("/api/saved", json={"item": ITEM})
        self.assertEqual(len(self.client.get("/api/saved").json()["items"]), 1)

        other = self.new_client()
        self.register(other, email="baska@example.com")
        self.assertEqual(other.get("/api/saved").json()["items"], [])
        other.delete("/api/saved", params={"url": ITEM["url"]})
        self.assertEqual(len(self.client.get("/api/saved").json()["items"]), 1)

        self.assertEqual(self.client.delete("/api/saved", params={"url": ITEM["url"]}).status_code, 204)
        self.assertEqual(self.client.get("/api/saved").json()["items"], [])

    def test_unsafe_items_are_rejected_and_import_skips_them(self):
        self.register()
        bad = {**ITEM, "url": "javascript:alert(1)"}
        self.assertEqual(self.client.put("/api/saved", json={"item": bad}).status_code, 400)
        imported = self.client.post("/api/saved/import", json={"items": [bad, ITEM, {**ITEM, "url": "https://example.com/b"}]})
        self.assertEqual(imported.status_code, 200)
        self.assertEqual(imported.json()["skipped"], 1)
        self.assertEqual({i["url"] for i in imported.json()["items"]}, {ITEM["url"], "https://example.com/b"})

    def test_account_responses_are_not_cached(self):
        self.register()
        for path in ["/api/auth/me", "/api/saved"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).headers["cache-control"], "no-store")

    def test_weak_passwords_are_rejected(self):
        for password, reason in [("password123", "yaygın"), ("Galatasaray", "yaygın"), ("aaaaaaaaaa", "yaygın"),
                                 ("okur-2026!", "e-posta")]:
            with self.subTest(password=password):
                response = self.client.post("/api/auth/register", json={"email": "okur@example.com", "password": password})
                self.assertEqual(response.status_code, 400)
                self.assertIn(reason, response.json()["detail"]["message"])

    def test_registration_is_rate_limited_per_client(self):
        for n in range(auth.REGISTER_ATTEMPTS):
            self.assertEqual(self.register(self.new_client(), email=f"kisi{n}@example.com").status_code, 201)
        self.assertEqual(self.register(self.new_client(), email="fazla@example.com").status_code, 429)

    def test_password_hash_uses_strong_scrypt_and_old_hashes_are_upgraded(self):
        self.register()
        with database.connect(self.db) as db:
            self.assertTrue(db.execute("SELECT password_hash FROM users").fetchone()[0].startswith("scrypt$131072$8$1$"))
        with patch.dict(auth.SCRYPT, {"n": 2**14}):
            weak = auth.hash_password(PASSWORD)
        with database.connect(self.db) as db:
            db.execute("UPDATE users SET password_hash = ?", (weak,))
        self.assertEqual(self.new_client().post("/api/auth/login", json={"email": "okur@example.com", "password": PASSWORD}).status_code, 200)
        with database.connect(self.db) as db:
            upgraded = db.execute("SELECT password_hash FROM users").fetchone()[0]
        self.assertTrue(upgraded.startswith("scrypt$131072$"))
        self.assertTrue(auth.verify_password(PASSWORD, upgraded))

    def test_cross_site_changes_are_rejected(self):
        self.register()
        evil = {"origin": "https://kotu.example"}
        self.assertEqual(self.client.put("/api/saved", json={"item": ITEM}, headers=evil).status_code, 403)
        self.assertEqual(self.client.put("/api/saved", json={"item": ITEM}, headers={"sec-fetch-site": "cross-site"}).status_code, 403)
        self.assertEqual(self.client.get("/api/saved").json()["items"], [])
        same = {"origin": "http://testserver", "sec-fetch-site": "same-origin"}
        self.assertEqual(self.client.put("/api/saved", json={"item": ITEM}, headers=same).status_code, 200)

    def test_security_headers(self):
        page = self.client.get("/")
        self.assertIn("frame-ancestors 'none'", page.headers["content-security-policy"])
        self.assertIn("script-src 'self'", page.headers["content-security-policy"])
        self.assertEqual(page.headers["x-frame-options"], "DENY")
        self.assertEqual(page.headers["x-content-type-options"], "nosniff")
        self.assertNotIn("content-security-policy", self.client.get("/docs").headers)

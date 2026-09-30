"""Vercel'e özgü davranışlar: yapılandırma, cron, vekil sunucu başlıkları."""
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import tomllib
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.repositories import database
from backend.app.repositories import daily as repo
from backend.app.services import auth
from backend.app.services.collection import CollectionResult
from backend.app.services.daily import get_daily

ROOT = Path(__file__).resolve().parents[2]
DAY = date(2026, 9, 30)
SECRET = "cron-parolasi-en-az-16-karakter"


class ConfigurationTests(unittest.TestCase):
    def test_vercel_and_local_dependencies_match(self):
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        local = [line.strip() for line in (ROOT / "backend/requirements.txt").read_text(encoding="utf-8").splitlines()
                 if line.strip() and not line.startswith("#")]
        self.assertEqual(sorted(pyproject["project"]["dependencies"]), sorted(local))
        module, name = pyproject["tool"]["vercel"]["entrypoint"].split(":")
        self.assertEqual((module, name), ("backend.app.main", "app"))

    def test_crons_are_daily_and_point_to_existing_route(self):
        config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
        self.assertIn("backend/app/main.py", config["functions"])
        client = TestClient(app)
        self.addCleanup(client.close)
        for cron in config["crons"]:
            with self.subTest(cron=cron):
                minute, hour, *rest = cron["schedule"].split()
                # Hobby planı: her görev günde en fazla bir kez.
                self.assertTrue(minute.isdigit() and hour.isdigit())
                self.assertEqual(rest, ["*", "*", "*"])
                # Rota var ama parolasız çağrı reddedilir (404 değil 401).
                self.assertEqual(client.get(cron["path"]).status_code, 401)


class VercelBehaviourTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "deploy.sqlite3"
        patch.object(database, "DATABASE", self.db).start()
        self.collect = patch("backend.app.services.daily.collect_contents", return_value=CollectionResult([], {"ok": 0}, {}, 0)).start()
        patch("backend.app.services.daily.today", return_value=DAY).start()
        patch("backend.app.api.cron_routes.today", return_value=DAY).start()
        patch("backend.app.api.daily_routes.today", return_value=DAY).start()
        patch.object(auth, "login_limiter", auth.AttemptLimiter()).start()
        patch.object(auth, "register_limiter", auth.AttemptLimiter(auth.REGISTER_ATTEMPTS, auth.REGISTER_WINDOW_SECONDS)).start()
        self.addCleanup(patch.stopall)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    @contextmanager
    def vercel(self, **extra):
        # Testler geçici SQLite kullanır; Vercel'in "SQLite kullanma" koruması ayrı sınanır.
        with patch.dict(os.environ, {"VERCEL": "1", **extra}),                 patch("backend.app.repositories.database.running_on_vercel", return_value=False):
            yield

    def test_cron_requires_secret(self):
        with self.vercel(CRON_SECRET=SECRET):
            self.assertEqual(self.client.get("/api/cron/daily").status_code, 401)
            self.assertEqual(self.client.get("/api/cron/daily", headers={"authorization": "Bearer yanlis"}).status_code, 401)
            ok = self.client.get("/api/cron/daily", headers={"authorization": f"Bearer {SECRET}"})
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()["date"], DAY.isoformat())
        with repo.connect(self.db) as db:
            self.assertEqual(repo.list_dates(db), [DAY.isoformat()])
        # Parola hiç tanımlanmamışsa boş "Bearer " ile de açılmaz.
        with patch.dict(os.environ, {"CRON_SECRET": ""}):
            self.assertEqual(self.client.get("/api/cron/daily", headers={"authorization": "Bearer "}).status_code, 401)

    def test_stale_edition_is_not_refreshed_in_a_thread_on_vercel(self):
        get_daily(DAY, self.db)
        with repo.connect(self.db) as db:
            edition = repo.read_edition(db, DAY.isoformat())
            edition["topic_shortfalls"] = {"kitap": 2}
            edition["generated_at"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            repo.save_edition(db, edition)
        self.collect.reset_mock()
        with self.vercel(), patch("backend.app.services.daily.refresh_in_background") as thread:
            self.assertEqual(get_daily(DAY, self.db, wait_for_refresh=False), edition)
        thread.assert_not_called()
        self.collect.assert_not_called()

    def test_https_behind_vercel_proxy_is_recognised(self):
        headers = {"x-forwarded-proto": "https", "x-forwarded-host": "gunluk-kesif.vercel.app",
                   "origin": "https://gunluk-kesif.vercel.app", "x-real-ip": "203.0.113.7"}
        with self.vercel():
            response = self.client.post("/api/auth/register", json={"email": "okur@example.com", "password": "gizli-parola-1"}, headers=headers)
            self.assertEqual(response.status_code, 201)
            self.assertIn("secure", response.headers["set-cookie"].lower())
            self.assertIn("max-age=", response.headers["strict-transport-security"])
            evil = {**headers, "origin": "https://kotu.example"}
            self.assertEqual(self.client.post("/api/auth/logout", headers=evil).status_code, 403)

    def test_forwarded_headers_are_ignored_locally(self):
        spoofed = {"x-forwarded-proto": "https", "x-forwarded-host": "kotu.example", "origin": "https://kotu.example"}
        self.assertEqual(self.client.post("/api/auth/logout", headers=spoofed).status_code, 403)
        self.assertNotIn("strict-transport-security", self.client.get("/", headers=spoofed).headers)

    def test_sqlite_is_refused_on_vercel(self):
        with patch.dict(os.environ, {"VERCEL": "1"}), self.assertRaises(RuntimeError):
            with database.connect(self.db):
                pass

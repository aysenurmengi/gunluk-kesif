"""Günlük seçki testlerini gerçek PostgreSQL üzerinde tekrar çalıştır.

TEST_DATABASE_URL tanımlı değilse atlanır. Bu veritabanındaki tablolar her
testte boşaltılır; asıl DATABASE_URL veritabanını burada kullanma.
"""
import os
import unittest

import test_auth
import test_daily
import test_matching_and_pool
from backend.app.repositories import daily as repo

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
requires_postgres = unittest.skipUnless(
    repo.is_postgres(TEST_DATABASE_URL), "TEST_DATABASE_URL (postgresql://...) tanımlı değil")


class EmptyPostgresMixin:
    def setUp(self):
        super().setUp()
        self.db = TEST_DATABASE_URL
        with repo.connect(self.db) as db:
            db.execute("TRUNCATE recommendations, editions, pool, saved_items, sessions, users")


@requires_postgres
class PostgresDailyTests(EmptyPostgresMixin, test_daily.DailyTests):
    pass


@requires_postgres
class PostgresPoolAndRefreshTests(EmptyPostgresMixin, test_matching_and_pool.PoolAndRefreshTests):
    pass


@requires_postgres
class PostgresAuthTests(test_auth.AuthTests):
    def use_database(self):
        self.db = TEST_DATABASE_URL
        with repo.connect(self.db) as db:
            db.execute("TRUNCATE saved_items, sessions, users")
        super().use_database()


@requires_postgres
class PostgresTypeTests(EmptyPostgresMixin, unittest.TestCase):
    def test_columns_use_native_types(self):
        with repo.connect(self.db) as db:
            types = dict(db.execute(
                "SELECT table_name || '.' || column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name IN ('pool', 'editions', 'recommendations')").fetchall())
        self.assertEqual(types["editions.day"], "date")
        self.assertEqual(types["editions.payload"], "jsonb")
        self.assertEqual(types["pool.payload"], "jsonb")

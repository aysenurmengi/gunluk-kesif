"""Arayüz dosyalarının sunulması ve önbellek davranışı; canlı RSS çağrısı yapılmaz."""

import unittest

from fastapi.testclient import TestClient

from backend.app.main import app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_frontend_and_modules_are_served_from_same_app(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="data-status"', response.text)
        self.assertNotIn("Tasarım önizlemesi", response.text)
        for path in ["/css/styles.css", "/js/app.js", "/js/services/api.js", "/js/data/topics.js", "/js/components/content-card.js"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        self.assertEqual(self.client.get("/openapi.json").status_code, 200)

    def test_project_files_and_unknown_api_paths_are_not_served(self):
        for path in ["/serve.py", "/backend/app/main.py", "/.env", "/api/unknown"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_frontend_revalidates_even_for_conditional_module_requests(self):
        for path in ["/", "/index.html", "/js/app.js?v=topic-fix-1", "/js/services/api.js?v=topic-fix-1", "/js/data/topics.js?v=topic-fix-1", "/css/styles.css"]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["cache-control"], "no-cache")
                cached = self.client.get(path, headers={"If-None-Match": response.headers["etag"]})
                self.assertEqual(cached.status_code, 304)
                self.assertEqual(cached.headers["cache-control"], "no-cache")

    def test_source_notes_are_initially_collapsed_and_topic_name_is_technology(self):
        html = self.client.get("/").text
        self.assertIn('<details id="selection-notes" class="selection-notes" hidden>', html)
        self.assertNotIn('id="source-warning" class="data-notice error"', html)
        topics = self.client.get("/js/data/topics.js?v=catalog-1").text
        self.assertIn('name: "Teknoloji"', topics)
        self.assertNotIn('name: "Yapay zekâ"', topics)

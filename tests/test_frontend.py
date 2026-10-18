import unittest

from fastapi.testclient import TestClient

from src.api.app import app


class FrontendTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_dashboard_is_served_from_root(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("Order operations", response.text)

    def test_dashboard_assets_are_served(self):
        css_response = self.client.get("/assets/dashboard.css")
        js_response = self.client.get("/assets/dashboard.js")
        self.assertEqual(css_response.status_code, 200)
        self.assertIn("text/css", css_response.headers["content-type"])
        self.assertEqual(js_response.status_code, 200)
        self.assertIn("javascript", js_response.headers["content-type"])


if __name__ == "__main__":
    unittest.main()
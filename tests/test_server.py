import http.client
import json
import threading
import unittest
from urllib.parse import urlencode

from src.server import make_server


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.server = make_server("127.0.0.1", 0)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection(
            "127.0.0.1",
            self.port,
            timeout=2,
        )
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_home_page_contains_url_form(self):
        status, headers, body = self.request("GET", "/")

        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn(b'<form action="/shorten" method="post">', body)
        self.assertIn(b'name="url"', body)

    def test_form_submission_shows_short_link_that_redirects(self):
        url = "https://example.com/path?query=value"
        body = urlencode({"url": url})
        status, _, response_body = self.request(
            "POST",
            "/shorten",
            body=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        self.assertEqual(status, 200)
        self.assertIn(b"http://127.0.0.1:", response_body)
        self.assertIn(b"/0", response_body)

        status, headers, _ = self.request("GET", "/0")
        self.assertEqual(status, 302)
        self.assertEqual(headers["Location"], url)

    def test_json_api_uses_forwarded_origin_and_validates_input(self):
        status, headers, body = self.request(
            "POST",
            "/shorten",
            body=json.dumps({"url": "https://example.com/json"}),
            headers={
                "Content-Type": "application/json",
                "X-Forwarded-Proto": "https",
                "X-Forwarded-Host": "short.example",
            },
        )

        self.assertEqual(status, 200)
        self.assertIn("application/json", headers["Content-Type"])
        self.assertEqual(
            json.loads(body),
            {"code": "0", "short_url": "https://short.example/0"},
        )

        status, _, error_body = self.request(
            "POST",
            "/shorten",
            body="{invalid",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 400)
        self.assertIn("error", json.loads(error_body))

    def test_table_shows_chains_and_expandable_horner_calculation(self):
        self.request(
            "POST",
            "/shorten",
            body=urlencode({"url": "https://example.com/table"}),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        status, _, body = self.request("GET", "/table")

        self.assertEqual(status, 200)
        self.assertIn(b"NULL", body)
        self.assertIn(b"&rarr;", body)
        self.assertIn(b"URL:</strong>", body)
        self.assertIn(b"Code:</strong>", body)
        self.assertIn(b"Short link:</strong>", body)
        self.assertIn(b"<details>", body)
        self.assertIn(b"Horner hash calculation", body)
        self.assertIn(b"ord(", body)

    def test_unknown_short_code_returns_not_found(self):
        status, _, _ = self.request("GET", "/not-registered")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()

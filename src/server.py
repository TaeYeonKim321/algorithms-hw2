"""HTTP interface for the in-memory URL shortener."""

import argparse
import html
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.shortener import URLShortener


_MAX_REQUEST_SIZE = 16_384


def _page(title: str, content: str) -> str:
    safe_title = html.escape(title)
    return (
        "<!doctype html>"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{safe_title}</title>"
        "<style>"
        "body{font:16px sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem}"
        "input[type=url]{box-sizing:border-box;width:min(100%,42rem);padding:.6rem}"
        "button{padding:.6rem 1rem;margin-top:.7rem}"
        "table{border-collapse:collapse;width:100%}"
        "th,td{border:1px solid #bbb;padding:.6rem;text-align:left;vertical-align:top}"
        ".chain-node{display:inline-block;max-width:100%;overflow-wrap:anywhere}"
        ".error{color:#a00}"
        "code{overflow-wrap:anywhere}"
        "</style></head><body>"
        f"<h1>{safe_title}</h1>{content}</body></html>"
    )


class ShortenerHTTPServer(HTTPServer):
    """HTTP server holding one in-memory shortener instance."""

    def __init__(
        self,
        server_address: tuple[str, int],
        shortener: URLShortener | None = None,
    ):
        self.shortener = shortener if shortener is not None else URLShortener()
        super().__init__(server_address, ShortenerRequestHandler)


class ShortenerRequestHandler(BaseHTTPRequestHandler):
    """Serve the browser form, redirect links, and hash-table view."""

    server: ShortenerHTTPServer

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/":
            content = (
                "<p>Enter an absolute HTTP or HTTPS URL to shorten.</p>"
                '<form action="/shorten" method="post">'
                '<label for="url">URL</label><br>'
                '<input id="url" name="url" type="url" maxlength="2048" required>'
                '<br><button type="submit">Shorten</button></form>'
                '<p><a href="/table">View hash table</a></p>'
            )
            self._send_html(200, _page("URL shortener", content))
            return

        if path == "/table":
            self._send_html(200, _page("Hash table", self._table_content()))
            return

        code = path.removeprefix("/")
        if code and "/" not in code:
            try:
                url = self.server.shortener.expand(code)
            except (KeyError, ValueError):
                self._send_html(404, _page("Not found", "<p>Short link not found.</p>"))
                return
            self.send_response(302)
            self.send_header("Location", url)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        self._send_html(404, _page("Not found", "<p>Page not found.</p>"))

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/shorten":
            self._send_html(404, _page("Not found", "<p>Page not found.</p>"))
            return

        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip()
        is_json = content_type == "application/json"
        try:
            body = self._read_body()
            if is_json:
                url = self._url_from_json(body)
            elif content_type == "application/x-www-form-urlencoded":
                url = self._url_from_form(body)
            else:
                self._send_html(
                    415,
                    _page("Unsupported media type", "<p>Use a URL form or JSON request.</p>"),
                )
                return
            code = self.server.shortener.shorten(url)
        except _ResponseSent:
            return
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            self._send_submission_error(str(error), is_json)
            return

        short_url = self._short_url(code)
        if is_json:
            self._send_json(200, {"code": code, "short_url": short_url})
            return

        safe_url = html.escape(short_url, quote=True)
        content = (
            '<p>Your short link is ready:</p>'
            f'<p><a href="{safe_url}">{html.escape(short_url)}</a></p>'
            '<p><a href="/">Shorten another URL</a></p>'
        )
        self._send_html(200, _page("Short URL created", content))

    def _read_body(self) -> bytes:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise ValueError("Content-Length is required")
        try:
            length = int(raw_length)
        except ValueError:
            raise ValueError("Invalid Content-Length") from None
        if length < 0:
            raise ValueError("Invalid Content-Length")
        if length > _MAX_REQUEST_SIZE:
            self._send_html(413, _page("Request too large", "<p>Request body is too large.</p>"))
            raise _ResponseSent
        return self.rfile.read(length)

    @staticmethod
    def _url_from_json(body: bytes) -> str:
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("url"), str):
            raise ValueError('JSON body must be an object with a string "url" field')
        return payload["url"]

    @staticmethod
    def _url_from_form(body: bytes) -> str:
        fields = parse_qsl(body.decode("utf-8"), keep_blank_values=True, max_num_fields=16)
        urls = [value for name, value in fields if name == "url"]
        if len(urls) != 1:
            raise ValueError('Form must contain exactly one "url" field')
        return urls[0]

    def _send_submission_error(self, message: str, is_json: bool) -> None:
        if is_json:
            self._send_json(400, {"error": message})
            return
        safe_message = html.escape(message)
        content = (
            f'<p class="error">{safe_message}</p>'
            '<p><a href="/">Try again</a></p>'
        )
        self._send_html(400, _page("Could not shorten URL", content))

    def _short_url(self, code: str) -> str:
        scheme = self.headers.get("X-Forwarded-Proto", "http").split(",", 1)[0].strip()
        if scheme.lower() not in ("http", "https"):
            scheme = "http"
        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host")
        if not host:
            address, port = self.server.server_address[:2]
            host = f"{address}:{port}"
        return f"{scheme}://{host}/{code}"

    def _table_content(self) -> str:
        table = self.server.shortener._url_to_code
        rows = []
        for bucket_index, head in enumerate(table._buckets):
            nodes = []
            node = head
            while node is not None:
                short_url = self._short_url(node.value)
                safe_url = html.escape(node.key)
                safe_code = html.escape(node.value)
                safe_short_url = html.escape(short_url, quote=True)
                details = self._hash_details(node.key, table.bucket_count)
                nodes.append(
                    '<span class="chain-node">'
                    f"<strong>URL:</strong> <code>{safe_url}</code><br>"
                    f"<strong>Code:</strong> <code>{safe_code}</code><br>"
                    f'<strong>Short link:</strong> <a href="{safe_short_url}">'
                    f"{html.escape(short_url)}</a><br>{details}</span>"
                )
                node = node.next
            chain = " &rarr; ".join(nodes) if nodes else ""
            if chain:
                chain += " &rarr; "
            chain += "NULL"
            rows.append(
                f"<tr><th scope=\"row\">{bucket_index}</th><td>{chain}</td></tr>"
            )
        return (
            "<p>URL-to-code buckets; each chain ends at NULL.</p>"
            "<table><thead><tr><th>Bucket</th><th>Linked list</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
            '<p><a href="/">Back to URL shortener</a></p>'
        )

    @staticmethod
    def _hash_details(key: str, bucket_count: int) -> str:
        steps = ["<li>Start with h = 0.</li>"]
        value = 0
        for character in key:
            next_value = (value * 31 + ord(character)) % bucket_count
            steps.append(
                "<li>"
                f"h = ({value} &times; 31 + ord({html.escape(repr(character))})) "
                f"mod {bucket_count} = {next_value}</li>"
            )
            value = next_value
        steps.append(f"<li>Final bucket: {value}</li>")
        return (
            "<details><summary>Horner hash calculation</summary>"
            f"<ol>{''.join(steps)}</ol></details>"
        )

    def _send_html(self, status: int, document: str) -> None:
        body = document.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)


class _ResponseSent(Exception):
    """Indicate that the request handler already sent an error response."""


def make_server(host: str = "", port: int = 8000) -> ShortenerHTTPServer:
    """Create the HTTP server used by the command line and tests."""
    return ShortenerHTTPServer((host, port))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the URL shortener web server.")
    parser.add_argument("--port", type=int, default=8000)
    arguments = parser.parse_args()
    server = make_server(port=arguments.port)
    print(f"Serving URL shortener on port {arguments.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

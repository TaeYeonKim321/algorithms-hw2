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

from src.linear_probing_hash_table import LinearProbingHashTable, _Entry, _TOMBSTONE
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
        '<nav><a href="/">Home</a> | <a href="/table">Hash table</a> | '
        '<a href="/linear">Linear probing</a> | '
        '<a href="/linear/table">Linear table</a></nav>'
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
        self.linear_shortener = URLShortener(table_type="linear")
        super().__init__(server_address, ShortenerRequestHandler)


class ShortenerRequestHandler(BaseHTTPRequestHandler):
    """Serve the browser form, redirect links, and hash-table view."""

    server: ShortenerHTTPServer

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/":
            self._send_html(200, _page("URL shortener", self._form_content(False)))
            return

        if path == "/table":
            self._send_html(200, _page("Hash table", self._table_content()))
            return

        if path == "/linear":
            self._send_html(
                200,
                _page("Linear probing URL shortener", self._form_content(True)),
            )
            return

        if path == "/linear/table":
            self._send_html(
                200,
                _page("Linear probing table", self._linear_table_content()),
            )
            return

        if path.startswith("/linear/s/"):
            code = path.removeprefix("/linear/s/")
            if not code or "/" in code:
                self._send_html(404, _page("Not found", "<p>Short link not found.</p>"))
                return
            try:
                url = self.server.linear_shortener.expand(code)
            except (KeyError, ValueError):
                self._send_html(404, _page("Not found", "<p>Short link not found.</p>"))
                return
            self._send_redirect(url)
            return

        code = path.removeprefix("/")
        if code and "/" not in code:
            try:
                url = self.server.shortener.expand(code)
            except (KeyError, ValueError):
                self._send_html(404, _page("Not found", "<p>Short link not found.</p>"))
                return
            self._send_redirect(url)
            return

        self._send_html(404, _page("Not found", "<p>Page not found.</p>"))

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path == "/shorten":
            linear = False
        elif path == "/linear/shorten":
            linear = True
        else:
            self._send_html(404, _page("Not found", "<p>Page not found.</p>"))
            return

        shortener = (
            self.server.linear_shortener if linear else self.server.shortener
        )
        home_path = "/linear" if linear else "/"
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
            code = shortener.shorten(url)
        except _ResponseSent:
            return
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            self._send_submission_error(str(error), is_json, home_path)
            return

        short_url = self._short_url(code, linear)
        if is_json:
            self._send_json(200, {"code": code, "short_url": short_url})
            return

        safe_url = html.escape(short_url, quote=True)
        content = (
            '<p>Your short link is ready:</p>'
            f'<p><a href="{safe_url}">{html.escape(short_url)}</a></p>'
            f'<p><a href="{home_path}">Shorten another URL</a></p>'
        )
        self._send_html(200, _page("Short URL created", content))

    @staticmethod
    def _form_content(linear: bool) -> str:
        action = "/linear/shorten" if linear else "/shorten"
        return (
            "<p>Enter an absolute HTTP or HTTPS URL to shorten.</p>"
            f'<form action="{action}" method="post">'
            '<label for="url">URL</label><br>'
            '<input id="url" name="url" type="url" maxlength="2048" required>'
            '<br><button type="submit">Shorten</button></form>'
        )

    def _send_redirect(self, url: str) -> None:
        self.send_response(302)
        self.send_header("Location", url)
        self.send_header("Content-Length", "0")
        self.end_headers()

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

    def _send_submission_error(
        self,
        message: str,
        is_json: bool,
        home_path: str = "/",
    ) -> None:
        if is_json:
            self._send_json(400, {"error": message})
            return
        safe_message = html.escape(message)
        content = (
            f'<p class="error">{safe_message}</p>'
            f'<p><a href="{home_path}">Try again</a></p>'
        )
        self._send_html(400, _page("Could not shorten URL", content))

    def _short_url(self, code: str, linear: bool = False) -> str:
        scheme = self.headers.get("X-Forwarded-Proto", "http").split(",", 1)[0].strip()
        if scheme.lower() not in ("http", "https"):
            scheme = "http"
        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host")
        if not host:
            address, port = self.server.server_address[:2]
            host = f"{address}:{port}"
        path = f"/linear/s/{code}" if linear else f"/{code}"
        return f"{scheme}://{host}{path}"

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

    def _linear_table_content(self) -> str:
        table = self.server.linear_shortener._url_to_code
        rows = []
        for index, slot in enumerate(table._slots):
            if slot is None:
                content = "<span>비어 있음</span>"
            elif slot is _TOMBSTONE:
                content = "<span>삭제 표시</span>"
            elif isinstance(slot, _Entry):
                short_url = self._short_url(slot.value, linear=True)
                safe_url = html.escape(slot.key)
                safe_code = html.escape(slot.value)
                safe_short_url = html.escape(short_url, quote=True)
                details = self._linear_probe_details(slot.key, table)
                content = (
                    '<span class="chain-node">'
                    f"<strong>URL:</strong> <code>{safe_url}</code><br>"
                    f"<strong>Code:</strong> <code>{safe_code}</code><br>"
                    f'<strong>Short link:</strong> <a href="{safe_short_url}">'
                    f"{html.escape(short_url)}</a><br>{details}</span>"
                )
            else:
                raise RuntimeError("linear probing table contains an unknown slot")
            rows.append(
                f'<tr><th scope="row">{index}</th><td>{content}</td></tr>'
            )
        return (
            "<p>Linear probing slots in index order.</p>"
            "<table><thead><tr><th>Slot</th><th>State / item</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
            '<p><a href="/linear">Back to linear probing</a></p>'
        )

    @staticmethod
    def _linear_probe_details(
        key: str,
        table: LinearProbingHashTable[str],
    ) -> str:
        value = 0
        hash_steps = ["<li>Start with h = 0.</li>"]
        for character in key:
            next_value = (value * 31 + ord(character)) % table.bucket_count
            hash_steps.append(
                "<li>"
                f"h = ({value} &times; 31 + ord({html.escape(repr(character))})) "
                f"mod {table.bucket_count} = {next_value}</li>"
            )
            value = next_value

        checked = []
        found_index = None
        for offset in range(table.bucket_count):
            index = (value + offset) % table.bucket_count
            slot = table._slots[index]
            if slot is None:
                state = "empty"
            elif slot is _TOMBSTONE:
                state = "deleted"
            elif isinstance(slot, _Entry):
                state = "occupied"
                if slot.key == key:
                    found_index = index
            else:
                raise RuntimeError("linear probing table contains an unknown slot")
            checked.append(f"{index} ({state})")
            if found_index is not None or slot is None:
                break

        probe_path = " &rarr; ".join(item.split(" ", 1)[0] for item in checked)
        hash_steps.append(f"<li>Start slot: {value}</li>")
        hash_steps.append(
            "<li>Probed slots: " + "; ".join(checked) + "</li>"
        )
        hash_steps.append(
            f"<li>Probe path: {probe_path}</li>"
        )
        if found_index is not None:
            hash_steps.append(f"<li>Found key at slot {found_index}.</li>")
        return (
            "<details><summary>Horner hash and probe path</summary>"
            f"<ol>{''.join(hash_steps)}</ol></details>"
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

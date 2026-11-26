"""In-memory URL shortener backed by the project's custom hash table."""

import unicodedata
from urllib.parse import urlsplit

from src.base62 import decode, encode
from src.hash_table import HashTable


class URLShortener:
    """Assign sequential base62 codes to valid HTTP(S) URLs."""

    def __init__(self):
        self._url_to_code: HashTable[str] = HashTable()
        self._code_to_url: HashTable[str] = HashTable()
        self._next_id = 0

    def shorten(self, url: str) -> str:
        """Return the existing or newly assigned code for a valid URL."""
        self._validate_url(url)
        try:
            return self._url_to_code.get(url)
        except KeyError:
            code = encode(self._next_id)
            self._next_id += 1
            self._url_to_code.set(url, code)
            self._code_to_url.set(code, url)
            return code

    def expand(self, code: str) -> str:
        """Return the URL for a valid, registered base62 code."""
        decode(code)
        return self._code_to_url.get(code)

    @staticmethod
    def _validate_url(url: str) -> None:
        if not isinstance(url, str):
            raise ValueError("URL must be a string")
        if not url or len(url) > 2048:
            raise ValueError("URL must contain between 1 and 2048 characters")
        if any(
            character.isspace() or unicodedata.category(character) == "Cc"
            for character in url
        ):
            raise ValueError("URL must not contain whitespace or control characters")

        try:
            parsed = urlsplit(url)
            parsed.port
        except ValueError as error:
            raise ValueError(f"invalid URL: {error}") from None

        if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
            raise ValueError("URL must be an absolute HTTP or HTTPS URL with a host")

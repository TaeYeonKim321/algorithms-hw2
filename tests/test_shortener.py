import unittest

from src.shortener import URLShortener


class URLShortenerTests(unittest.TestCase):
    def setUp(self):
        self.shortener = URLShortener()

    def test_first_url_uses_zero_and_distinct_urls_get_distinct_codes(self):
        first_url = "https://example.com/first"
        second_url = "https://example.com/second"

        first_code = self.shortener.shorten(first_url)
        second_code = self.shortener.shorten(second_url)

        self.assertEqual(first_code, "0")
        self.assertNotEqual(first_code, second_code)
        self.assertEqual(self.shortener.expand(first_code), first_url)
        self.assertEqual(self.shortener.expand(second_code), second_url)

    def test_shortening_same_url_again_returns_same_code(self):
        url = "https://example.com/repeated"

        first_code = self.shortener.shorten(url)
        repeated_code = self.shortener.shorten(url)
        next_code = self.shortener.shorten("https://example.com/next")

        self.assertEqual(repeated_code, first_code)
        self.assertEqual(next_code, "1")

    def test_unknown_valid_base62_code_raises_key_error(self):
        with self.assertRaises(KeyError):
            self.shortener.expand("z")

    def test_invalid_base62_codes_raise_value_error(self):
        for code in ("", "?", "a/"):
            with self.subTest(code=code):
                with self.assertRaises(ValueError):
                    self.shortener.expand(code)

    def test_invalid_urls_are_rejected(self):
        invalid_urls = (
            "",
            " https://example.com/path",
            "https://example.com/path ",
            "https://example.com/has space",
            "https://example.com/has\nnewline",
            "ftp://example.com/path",
            "http:///path-without-host",
            "http://example.com:not-a-port/path",
            "https://example.com:99999/path",
        )
        for url in invalid_urls:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    self.shortener.shorten(url)

    def test_url_length_limit_includes_2048_and_rejects_2049(self):
        prefix = "https://example.com/"
        max_length_url = prefix + "x" * (2048 - len(prefix))
        too_long_url = prefix + "x" * (2049 - len(prefix))

        self.assertEqual(len(max_length_url), 2048)
        self.assertEqual(self.shortener.expand(self.shortener.shorten(max_length_url)), max_length_url)
        self.assertEqual(len(too_long_url), 2049)
        with self.assertRaises(ValueError):
            self.shortener.shorten(too_long_url)

    def test_path_query_and_fragment_are_preserved(self):
        url = "https://example.com/a/b?query=value&other=two#section"

        code = self.shortener.shorten(url)

        self.assertEqual(self.shortener.expand(code), url)


if __name__ == "__main__":
    unittest.main()

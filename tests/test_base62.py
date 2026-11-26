import unittest

from src.base62 import decode, encode


class Base62Tests(unittest.TestCase):
    def test_encode_uses_the_specified_digit_order(self):
        expected = {
            0: "0",
            9: "9",
            10: "a",
            35: "z",
            36: "A",
            61: "Z",
            62: "10",
        }
        for number, encoded in expected.items():
            with self.subTest(number=number):
                self.assertEqual(encode(number), encoded)

    def test_decode_uses_the_specified_digit_order(self):
        expected = {
            "0": 0,
            "9": 9,
            "a": 10,
            "z": 35,
            "A": 36,
            "Z": 61,
            "10": 62,
        }
        for encoded, number in expected.items():
            with self.subTest(encoded=encoded):
                self.assertEqual(decode(encoded), number)

    def test_round_trip_large_integers(self):
        for number in (0, 1, 62, 2**128, 10**100):
            with self.subTest(number=number):
                self.assertEqual(decode(encode(number)), number)

    def test_encode_rejects_negative_and_non_integer_values(self):
        with self.assertRaises(ValueError):
            encode(-1)
        for value in (1.5, "12", True):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    encode(value)

    def test_decode_rejects_empty_and_invalid_input(self):
        for encoded in ("", "a?", " 1"):
            with self.subTest(encoded=encoded):
                with self.assertRaises(ValueError):
                    decode(encoded)
        with self.assertRaises(TypeError):
            decode(62)


if __name__ == "__main__":
    unittest.main()

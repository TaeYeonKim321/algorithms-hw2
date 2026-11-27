"""Base62 conversion using the alphabet 0-9, a-z, A-Z."""

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def encode(n: int) -> str:
    """Encode a non-negative integer as a base62 string."""
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError("n must be an integer")
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return "0"

    digits = []
    while n:
        n, remainder = divmod(n, len(ALPHABET))
        digits.append(ALPHABET[remainder])
    return "".join(reversed(digits))


def decode(s: str) -> int:
    """Decode a non-empty base62 string to an integer."""
    if not isinstance(s, str):
        raise TypeError("s must be a string")
    if not s:
        raise ValueError("s must not be empty")

    value = 0
    for character in s:
        try:
            digit = ALPHABET.index(character)
        except ValueError:
            raise ValueError(f"invalid base62 character: {character!r}") from None
        value = value * len(ALPHABET) + digit
    return value

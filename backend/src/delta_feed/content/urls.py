from urllib.parse import urlsplit

MAX_URL_LENGTH = 2048


def safe_http_url(value: str | None) -> str | None:
    """Return a stripped absolute http(s) URL without credentials, else None."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value or len(value) > MAX_URL_LENGTH:
        return None
    if any(character.isspace() or ord(character) < 32 for character in value):
        return None
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not hostname:
        return None
    if parsed.username or parsed.password:
        return None
    return value

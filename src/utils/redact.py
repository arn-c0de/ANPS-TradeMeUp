from urllib.parse import urlparse


def redact_url(url: str) -> str:
    """Return a redacted display for a URL: scheme://hostname if available, 'SET' if present but host not parsable, or 'NOT SET' if falsy."""
    if not url:
        return "NOT SET"
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        scheme = parsed.scheme or ""
        if host:
            return f"{scheme}://{host}" if scheme else host
        return "SET"
    except Exception:
        return "SET"


def set_status(value) -> str:
    """Return 'SET' if value is truthy, otherwise 'NOT SET'."""
    return "SET" if value else "NOT SET"

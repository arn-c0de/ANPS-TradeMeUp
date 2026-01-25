from src.utils.redact import redact_url, set_status


def test_redact_url_with_full_url():
    url = "postgresql://user:pass@db.example.com:5432/db"
    assert redact_url(url) == "postgresql://db.example.com"


def test_redact_url_empty_or_none():
    assert redact_url("") == "NOT SET"
    assert redact_url(None) == "NOT SET"


def test_set_status():
    assert set_status("abc") == "SET"
    assert set_status("") == "NOT SET"
    assert set_status(None) == "NOT SET"

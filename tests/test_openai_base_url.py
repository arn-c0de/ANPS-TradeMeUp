from src.services.llm_service import DEFAULT_OPENAI_BASE_URL, normalize_openai_base_url


def test_normalize_openai_base_url_uses_default_for_empty_values():
    assert normalize_openai_base_url("") == DEFAULT_OPENAI_BASE_URL
    assert normalize_openai_base_url(None) == DEFAULT_OPENAI_BASE_URL
    assert normalize_openai_base_url("   ") == DEFAULT_OPENAI_BASE_URL


def test_normalize_openai_base_url_rejects_missing_scheme():
    assert normalize_openai_base_url("api.openai.com/v1") == DEFAULT_OPENAI_BASE_URL


def test_normalize_openai_base_url_accepts_valid_https_endpoint():
    assert (
        normalize_openai_base_url("https://example-proxy.local/v1")
        == "https://example-proxy.local/v1"
    )

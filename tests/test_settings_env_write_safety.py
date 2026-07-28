"""Guards for values the Settings tab writes into .env.local.

The app reads .env.local on startup, so a newline smuggled through a Dash State
value would let a caller append arbitrary variables (DATABASE_URL, API keys).
"""

import pytest

from src.gui.tabs.settings import (
    LLM_MODELS,
    _env_bool,
    _validate_model_name,
    _validate_provider,
)

ENV_INJECTIONS = [
    "ollama\nDATABASE_URL=postgresql://attacker/db",
    "ollama\rANTHROPIC_API_KEY=stolen",
    "gpt-4o-mini\nOPENAI_BASE_URL=http://evil.test",
    "model\n\nSECRET_KEY=owned",
]


@pytest.mark.parametrize("provider", list(LLM_MODELS))
def test_known_providers_accepted(provider):
    assert _validate_provider(provider) == provider


@pytest.mark.parametrize("bad", ENV_INJECTIONS + ["", None, "bogus", "OLLAMA"])
def test_unknown_providers_rejected(bad):
    with pytest.raises(ValueError):
        _validate_provider(bad)


@pytest.mark.parametrize(
    "model",
    [m["value"] for models in LLM_MODELS.values() for m in models],
)
def test_shipped_model_names_accepted(model):
    assert _validate_model_name(model) == model


@pytest.mark.parametrize("bad", ENV_INJECTIONS + ["", None, 42, "a" * 101, "has space"])
def test_model_names_with_newlines_or_junk_rejected(bad):
    with pytest.raises(ValueError):
        _validate_model_name(bad)


@pytest.mark.parametrize(
    "raw,expected",
    [
        (True, "true"),
        (False, "false"),
        ("true", "true"),
        ("yes", "true"),
        ("False", "false"),
        (None, "false"),
        ([], "false"),
        (["x"], "true"),
        ("true\nDATABASE_URL=postgresql://attacker/db", "false"),
    ],
)
def test_env_bool_always_yields_a_bare_literal(raw, expected):
    result = _env_bool(raw)
    assert result == expected
    assert result in {"true", "false"}
    assert "\n" not in result and "\r" not in result

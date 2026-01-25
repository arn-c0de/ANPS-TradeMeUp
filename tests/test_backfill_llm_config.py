from scripts.backfill_all_agents import print_llm_config
from src.config.settings import settings


def test_print_llm_config_redacts_keys_and_db(capsys, monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-SECRET-1234567890")
    monkeypatch.setattr(settings, "anthropic_api_key", "anth-SECRET-ABC")
    monkeypatch.setattr(settings, "ollama_base_url", "http://localhost:11434")
    monkeypatch.setattr(settings, "database_url", "postgresql://user:pass@db.example.com:5432/db")

    # Case 1: openai provider
    monkeypatch.setattr(settings, "llm_provider", "openai")
    print_llm_config()
    captured = capsys.readouterr().out

    # Ensure full secrets are not printed
    assert "sk-SECRET" not in captured
    assert "user:pass" not in captured
    assert "anth-SECRET" not in captured

    # Ensure masked/host info is present
    assert "Database: postgresql://db.example.com" in captured or "Database: SET" in captured
    assert "OpenAI API Key: SET" in captured

    # Case 2: anthropic provider
    monkeypatch.setattr(settings, "llm_provider", "anthropic")
    print_llm_config()
    captured2 = capsys.readouterr().out

    assert "anth-SECRET" not in captured2
    assert "Anthropic API Key: SET" in captured2

from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config import Settings


def test_settings_load_from_env(env_vars):
    s = Settings()
    assert s.openrouter_api_key == "test-openrouter-key"
    assert s.brave_api_key == "test-brave-key"
    assert s.telegram_bot_token == "test-telegram-token"
    assert s.telegram_chat_id == 123456789


def test_settings_defaults(env_vars):
    s = Settings()
    assert s.default_model == "anthropic/claude-sonnet-4-5"
    assert s.vault_path == Path("./vault/keypo-intel")
    assert s.briefing_hour == 7
    assert s.briefing_minute == 0
    assert s.timezone == "America/Los_Angeles"
    assert s.scrape_timeout == 15
    assert s.scrape_max_chars == 8000


def test_settings_missing_required_raises(monkeypatch, tmp_path):
    # chdir to tmp_path so pydantic-settings won't find the real .env
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    with pytest.raises(ValidationError):
        Settings()


def test_settings_custom_values(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "key1")
    monkeypatch.setenv("BRAVE_API_KEY", "key2")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "key4")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
    monkeypatch.setenv("DEFAULT_MODEL", "google/gemini-2.5-flash")
    monkeypatch.setenv("SCRAPE_MAX_CHARS", "5000")

    s = Settings()
    assert s.default_model == "google/gemini-2.5-flash"
    assert s.scrape_max_chars == 5000
    assert s.telegram_chat_id == 999

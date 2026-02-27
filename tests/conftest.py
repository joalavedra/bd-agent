import pytest

from src.config import Settings


@pytest.fixture
def env_vars(monkeypatch):
    """Set all required env vars to test values."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("BRAVE_API_KEY", "test-brave-key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-telegram-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")


@pytest.fixture
def settings(env_vars, tmp_path):
    """Return a Settings instance with vault pointing to tmp_path."""
    vault_path = tmp_path / "keypo-intel"
    vault_path.mkdir()
    for sub in ("Daily", "Companies", "People", "Topics", "Content Ideas", "Templates"):
        (vault_path / sub).mkdir()
    return Settings(
        openrouter_api_key="test-openrouter-key",
        brave_api_key="test-brave-key",
        telegram_bot_token="test-telegram-token",
        telegram_chat_id=123456789,
        vault_path=vault_path,
    )

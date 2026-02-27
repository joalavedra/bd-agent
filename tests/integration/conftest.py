import os

import pytest

from dotenv import load_dotenv

load_dotenv()

PLACEHOLDER_VALUES = {"", "test-openrouter-key", "test-brave-key", "test-telegram-token"}


def _require_key(name: str) -> str:
    val = os.environ.get(name, "")
    if not val or val in PLACEHOLDER_VALUES:
        pytest.skip(f"{name} not set or is a placeholder")
    return val


@pytest.fixture
def openrouter_key():
    return _require_key("OPENROUTER_API_KEY")


@pytest.fixture
def brave_key():
    return _require_key("BRAVE_API_KEY")


@pytest.fixture
def telegram_token():
    return _require_key("TELEGRAM_BOT_TOKEN")


@pytest.fixture
def telegram_chat_id():
    return int(_require_key("TELEGRAM_CHAT_ID"))


@pytest.fixture
def live_settings():
    """Return a real Settings instance from the environment."""
    _require_key("OPENROUTER_API_KEY")
    _require_key("BRAVE_API_KEY")
    _require_key("TELEGRAM_BOT_TOKEN")
    _require_key("TELEGRAM_CHAT_ID")
    from src.config import get_settings
    return get_settings()

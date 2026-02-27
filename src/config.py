from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # Required
    openrouter_api_key: str
    brave_api_key: str
    telegram_bot_token: str
    telegram_chat_id: int

    # Optional with defaults
    default_model: str = "anthropic/claude-sonnet-4-5"
    vault_path: Path = Path("./vault/keypo-intel")
    briefing_hour: int = 7
    briefing_minute: int = 0
    timezone: str = "America/Los_Angeles"
    scrape_timeout: int = 15
    scrape_max_chars: int = 8000
    scrape_thin_threshold: int = 300
    jina_api_key: str = ""
    jina_timeout: int = 30
    jina_fallback_enabled: bool = True


def get_settings() -> Settings:
    return Settings()

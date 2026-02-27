import pytest

from src.telegram_bot import send_briefing


async def test_send_test_message(live_settings):
    await send_briefing("Integration test: Telegram delivery confirmed.")
    print("Message sent to Telegram successfully")

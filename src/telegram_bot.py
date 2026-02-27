import structlog
from aiogram import Bot, Dispatcher, types

from src.agent import bd_agent, DEFAULT_MODEL
from src.config import get_settings

log = structlog.get_logger()

TELEGRAM_MAX_LENGTH = 4096

dp = Dispatcher()

_bot: Bot | None = None


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        settings = get_settings()
        _bot = Bot(token=settings.telegram_bot_token)
    return _bot


def _split_message(text: str) -> list[str]:
    """Split text into chunks that fit within Telegram's message limit."""
    if len(text) <= TELEGRAM_MAX_LENGTH:
        return [text]
    chunks = []
    while text:
        if len(text) <= TELEGRAM_MAX_LENGTH:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, TELEGRAM_MAX_LENGTH)
        if split_at == -1:
            split_at = TELEGRAM_MAX_LENGTH
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


async def send_briefing(text: str) -> None:
    """Send a message to the owner's chat. Used by the scheduler."""
    settings = get_settings()
    bot = get_bot()
    for chunk in _split_message(text):
        await bot.send_message(chat_id=settings.telegram_chat_id, text=chunk)


@dp.message()
async def handle_message(message: types.Message) -> None:
    settings = get_settings()

    if message.chat.id != settings.telegram_chat_id:
        await message.answer("Unauthorized.")
        return

    if not message.text:
        await message.answer("Please send a text message.")
        return

    try:
        result = await bd_agent.run(message.text, model=DEFAULT_MODEL)
        response = result.output
    except Exception as e:
        log.error("agent_error", error=str(e))
        response = f"Agent error: {e}"

    for chunk in _split_message(response):
        await message.answer(chunk)

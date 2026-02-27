import asyncio

from dotenv import load_dotenv

load_dotenv()

import structlog

from src.config import get_settings
from src.scheduler import setup_scheduler
from src.telegram_bot import dp, get_bot

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
)

log = structlog.get_logger()


async def main() -> None:
    settings = get_settings()
    log.info("starting", model=settings.default_model, vault=str(settings.vault_path))

    scheduler = setup_scheduler()
    scheduler.start()
    log.info("scheduler_started")

    bot = get_bot()
    try:
        log.info("telegram_polling_started")
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        log.info("shutdown_complete")


if __name__ == "__main__":
    asyncio.run(main())

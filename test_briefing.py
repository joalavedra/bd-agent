"""One-shot test: triggers the daily briefing job and prints results.

Usage:
    source .venv/bin/activate
    python test_briefing.py

What it does:
    1. Runs Phase 1 only (brief generation, no entity updates)
    2. Writes the briefing file to vault/keypo-intel/Daily/
    3. Sends the summary to your Telegram
    4. Prints the full agent output to your terminal

After running, check vault/keypo-intel/Daily/ for the generated .md file.
"""

import asyncio

from dotenv import load_dotenv

load_dotenv()

import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
)

from src.scheduler import daily_brief_only_job


async def main() -> None:
    print("=== Running daily briefing job (Phase 1 only) ===\n")
    await daily_brief_only_job()
    print("\n=== Done. Check vault/keypo-intel/Daily/ for the generated file. ===")


if __name__ == "__main__":
    asyncio.run(main())

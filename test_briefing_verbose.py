"""Verbose briefing test — traces every tool call the agent makes.

Usage:
    source .venv/bin/activate
    python test_briefing_verbose.py
"""

import asyncio
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from src.agent import bd_agent, DEFAULT_MODEL
from src.scheduler import DAILY_BRIEFING_PROMPT
from src.config import get_settings


async def main() -> None:
    settings = get_settings()
    print(f"=== Verbose Briefing Test — {datetime.now().isoformat()} ===\n")
    print(f"Model: {DEFAULT_MODEL}")
    print(f"Scrape max chars: {settings.scrape_max_chars}")
    print(f"Scrape timeout: {settings.scrape_timeout}s\n")
    print(f"Prompt:\n  {DAILY_BRIEFING_PROMPT[:200]}...\n")
    print("=" * 70)

    result = await bd_agent.run(DAILY_BRIEFING_PROMPT, model=DEFAULT_MODEL)

    # Walk through every message in the conversation
    for msg in result.all_messages():
        kind = msg.kind

        if kind == "request":
            for part in msg.parts:
                part_kind = getattr(part, "part_kind", None)
                if part_kind == "user-prompt":
                    print(f"\n{'='*70}")
                    print(f"USER PROMPT: {part.content[:200]}")
                elif part_kind == "tool-return":
                    content = str(part.content)
                    print(f"\n  TOOL RESULT ({part.tool_name}):")
                    # Show truncated content with length
                    if len(content) > 500:
                        print(f"    [{len(content)} chars] {content[:500]}...")
                    else:
                        print(f"    [{len(content)} chars] {content}")

        elif kind == "response":
            for part in msg.parts:
                part_kind = getattr(part, "part_kind", None)
                if part_kind == "tool-call":
                    args_str = str(part.args)
                    print(f"\n>> TOOL CALL: {part.tool_name}({args_str[:300]})")
                elif part_kind == "text":
                    print(f"\n{'='*70}")
                    print(f"AGENT FINAL RESPONSE [{len(part.content)} chars]:")
                    print(part.content[:1000])
                    if len(part.content) > 1000:
                        print(f"  ... ({len(part.content) - 1000} more chars)")

    print(f"\n{'='*70}")
    print("DONE")


if __name__ == "__main__":
    asyncio.run(main())

from pydantic_ai import Agent

from src.config import Settings, get_settings
from src.tools.vault import load_preferences
from src.tools import research, vault

_BASE_PROMPT = """\
You are a marketing intelligence agent for Keypo, a crypto security startup that \
provides seed phrase recovery using Shamir Secret Sharing across Apple devices.

You have two core jobs:

1. **Daily Marketing Brief** — Research and write an 8-section daily intelligence \
brief into the vault (Daily/ folder). Use search_web for discovery and scrape_url \
to read promising pages. scrape_url automatically falls back to a cloud renderer \
for JS-rendered pages. Check existing entities with list_all_entities for wikilink \
context. Do NOT create or modify entity files during briefing generation.

2. **Vault Entity Updates** — Read the daily brief and create/update entity files \
in Companies/, People/, Topics/, and Content Ideas/. Each entity has YAML \
frontmatter (type, status, stage, dates, tags) and an append-only Log section \
with [[Daily/YYYY-MM-DD]] backlinks. Always read an entity file fully before \
updating it — never overwrite without reading first. Write the complete file \
content (all frontmatter + all existing body + new entry) when updating.

Vault structure:
- Daily/ — Daily intelligence briefs (YYYY-MM-DD.md)
- Companies/ — Company profiles with CRM stage tracking
- People/ — Contact profiles
- Topics/ — Technology and market themes
- Content Ideas/ — Potential content pieces
- Templates/ — Read-only reference templates for entity files

Wikilink convention: Always use folder-prefixed wikilinks for unambiguous entity \
resolution: [[Companies/Acme Corp]], [[People/Jane Doe]], [[Topics/MPC Wallets]], \
[[Content Ideas/SSS Explainer Thread]].

CRM stages (tracked in company frontmatter `stage` field):
new → researched → outreach → in-conversation → closed | nurture

When given an ad-hoc request via Telegram, use the appropriate tools and respond \
concisely.

---

## Owner Preferences

"""


def _build_system_prompt() -> str:
    settings = get_settings()
    prefs = load_preferences(settings)
    if prefs:
        return _BASE_PROMPT + prefs
    return _BASE_PROMPT + "(No preferences set yet.)"


def _make_settings() -> Settings:
    return get_settings()


DEFAULT_MODEL = "openrouter:anthropic/claude-sonnet-4-5"

bd_agent = Agent(model=None)


@bd_agent.system_prompt
def _dynamic_system_prompt() -> str:
    return _build_system_prompt()


@bd_agent.tool
async def search_web(ctx, query: str, count: int = 5, freshness: str = "") -> list[dict]:
    """Search the web using Brave Search API. Optional freshness: 'pd' (past day), 'pw' (past week), 'pm' (past month)."""
    settings = _make_settings()
    return await research.search_web(query, settings, count=count, freshness=freshness or None)


@bd_agent.tool
async def scrape_url(ctx, url: str) -> dict:
    """Fetch a URL and convert its HTML content to markdown for analysis."""
    settings = _make_settings()
    return await research.scrape_url(url, settings)


@bd_agent.tool
async def write_note(ctx, folder: str, filename: str, content: str) -> str:
    """Write a markdown file to vault/{folder}/{filename}. Folders: Daily, Companies, People, Topics, Content Ideas."""
    settings = _make_settings()
    return await vault.write_note(folder, filename, content, settings)


@bd_agent.tool
async def read_note(ctx, folder: str, filename: str) -> str:
    """Read a markdown file from vault/{folder}/{filename}. Also works for Templates/."""
    settings = _make_settings()
    return await vault.read_note(folder, filename, settings)


@bd_agent.tool
async def list_notes(ctx, folder: str) -> list[str]:
    """List markdown filenames in vault/{folder}/."""
    settings = _make_settings()
    return await vault.list_notes(folder, settings)


@bd_agent.tool
async def list_all_entities(ctx) -> dict[str, list[str]]:
    """List all entity files across Companies/, People/, Topics/, Content Ideas/."""
    settings = _make_settings()
    return await vault.list_all_entities(settings)


@bd_agent.tool
async def update_preferences(ctx, content: str) -> str:
    """Update the agent's preferences.md file with new content."""
    settings = _make_settings()
    return await vault.update_preferences(content, settings)

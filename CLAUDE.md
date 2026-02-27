# BD Agent - Claude Code Instructions

## Project Overview

Autonomous marketing intelligence agent for Keypo, a crypto security startup (Shamir Secret Sharing across Apple devices). Runs as a single async Python process: Pydantic AI agent + aiogram Telegram bot + APScheduler cron job. Uses native Python tool functions (not MCP servers) for 60x less context overhead. Agent memory is a `preferences.md` file loaded into the system prompt on every run — same pattern as this file. CRM is file-based (YAML frontmatter entity files in the vault), not HubSpot.

## Build Order

Build incrementally. Run the test gate after each phase. Do not proceed if tests fail.

1. **Phase 1 — Core Agent & Tools**: `config.py`, `tools/research.py`, `tools/vault.py`, `agent.py`, seed `vault/preferences.md` → run phase 1 tests
2. **Phase 2 — Telegram Bot**: `telegram_bot.py` → run phase 2 tests
3. **Phase 3 — Scheduler**: `scheduler.py` → run phase 3 tests
4. **Phase 4 — Entrypoint**: `main.py` → run full offline suite
5. **Phase 4.5 — Integration Tests**: Write `tests/integration/` files (DO NOT RUN — they need real API keys the owner will provide)
6. **Phase 5 — Deployment**: `deploy/` files, `.env.example`

## Locked Decisions

| Layer | Choice | Notes |
|-------|--------|-------|
| Agent framework | Pydantic AI | Native tool functions, callable system prompts |
| LLM routing | OpenRouter | `pydantic-ai-slim[openrouter]` (slim build, not `pydantic-ai`) |
| Default model | `anthropic/claude-sonnet-4-5` | Via OpenRouter |
| Web search | Brave Search API | Direct httpx calls, no SDK |
| Web scraping | httpx + trafilatura (+ Jina Reader fallback) | trafilatura for content extraction, Jina for JS/blocked pages |
| HTTP client | httpx (async) | Single dep for search and scraping |
| Telegram | aiogram 3.x | Async, catch-all handler |
| Scheduler | APScheduler `AsyncIOScheduler` | Shares event loop with aiogram |
| CRM | File-based in vault (YAML frontmatter) | Entity files in Companies/, People/, Topics/, Content Ideas/ |
| Vault | Plain file I/O with pathlib | No database |
| Tools | Native Pydantic AI functions (7 total) | NOT MCP servers |

## Key Gotchas

- **System prompt must be a callable.** Pass the `_build_system_prompt` function reference to `Agent(system_prompt=...)`, not its return value. This ensures `preferences.md` is re-read on every `agent.run()` call.
- **`preferences.md` location**: `vault_path.parent / "preferences.md"` — sibling to the keypo-intel directory, not inside it.
- **`vault_path` default**: `./vault/keypo-intel` — contains Daily/, Companies/, People/, Topics/, Content Ideas/, Templates/ subdirectories.
- **Folder-prefixed wikilinks**: Always use `[[Companies/X]]`, `[[People/Y]]`, `[[Topics/Z]]`, `[[Content Ideas/W]]` — not bare `[[X]]`.
- **Templates/ is read-only.** `write_note` rejects writes to Templates/. `read_note` and `list_notes` can read it.
- **Entity files are append-only logs.** Never delete or modify existing log entries. Always read an entity file fully before updating.
- **`scrape_url` returns error dicts, not exceptions.** The agent needs to handle inaccessible pages gracefully in briefings, so errors come back as `{"markdown": "", "error": "...", "url": "...", "source": "error"}`.
- **Brave Search response path**: `data["web"]["results"]` — each item has `url`, `title`, `description`.
- **Truncate scraped content** to `SCRAPE_MAX_CHARS` (default 8000). Check raw text length against `scrape_thin_threshold` BEFORE truncating.
- **`trafilatura.extract()` can return `None`** — always handle `None` → `""`.
- **trafilatura can raise exceptions** on malformed HTML — always catch broadly.
- **Jina Reader fallback** triggers on thin trafilatura output (`< scrape_thin_threshold` chars), trafilatura exception, OR httpx fetch failure. Non-HTML content-type returns error dict directly — does NOT trigger Jina.
- **Content-type check** accepts both `text/html` and `application/xhtml+xml`.
- **trafilatura requires `libxml2-dev` and `libxslt-dev`** at build time (relevant for Docker).
- **Jina free tier** is ~20 RPM — API key recommended for production.
- **Telegram message limit**: 4096 chars. Split long agent responses into chunks.
- **APScheduler v3.x**: Use `AsyncIOScheduler`, not `BackgroundScheduler`.
- **One cron job, two chained phases.** Daily briefing generation → entity updates. Entity updates only run if the brief file exists. No separate CRM sync job.
- **Path traversal guard**: `write_note` and `read_note` resolve paths and check `is_relative_to(vault_path)`.

## Testing

```bash
# Offline suite (no API keys needed) — run this:
pytest tests/ -v --tb=short --ignore=tests/integration

# NEVER run tests/integration/ — those need real API keys the owner will provide.
```

- Mock all HTTP with `respx`. Mock Telegram with `AsyncMock`.
- Use `tmp_path` for vault filesystem tests (real filesystem, temp directory).
- All env vars via `monkeypatch.setenv` in shared conftest fixtures.
- `pyproject.toml` excludes integration tests by default (`addopts = "--ignore=tests/integration"`).
- Target <5 seconds for the full offline suite.

## Reference

Full specification: see `SPEC.md` in the project root.

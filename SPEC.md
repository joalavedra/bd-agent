# Keypo BD Agent — Build Specification

> **Purpose**: Complete specification for an autonomous marketing intelligence agent. Designed to be passed directly to Claude Code for implementation. All architectural decisions are pre-made. Implementation details are intentionally left to Claude Code — write idiomatic, tested code that satisfies the behavioral contracts described here.

---

## 1. What This Agent Does

A marketing intelligence agent for Keypo, a crypto security startup that provides seed phrase recovery using Shamir Secret Sharing across Apple devices.

One daily cron job with two chained phases, running on autopilot:

1. **Phase 1 — Daily Marketing Brief** — Discovers and researches potential partners, customers, competitors, and content opportunities. Writes an 8-section daily intelligence brief with `[[wikilinks]]` to entities. Uses Brave Search API for discovery and httpx + trafilatura for scraping pages.
2. **Phase 2 — Vault Entity Updates** — Reads the daily brief, extracts wikilinked entities, and creates/updates persistent company/people/topic/content-idea files with YAML frontmatter and append-only logs.

The agent also takes interactive commands via Telegram — the owner can message from their phone to trigger ad-hoc research, ask questions, or run manual operations.

---

## 2. Architecture Decisions (Do Not Change)

These are locked. Claude Code should follow them exactly.

### Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Agent framework | Pydantic AI | Native tool functions, callable system prompts |
| LLM routing | OpenRouter | One-line model swaps, pay-per-token |
| Default model | `anthropic/claude-sonnet-4-5` | Best tool calling reliability for development |
| Web search | Brave Search API via httpx | Usage-based (free tier: 2,000 queries/month) |
| Web scraping | httpx + trafilatura (+ Jina Reader fallback) | Content-focused extraction, Jina handles JS/blocked pages |
| Telegram | aiogram 3.x | Async, Pydantic-native |
| Scheduler | APScheduler `AsyncIOScheduler` | In-process, shares event loop |
| CRM | File-based in vault (YAML frontmatter) | Entity files with append-only logs, no external API |
| Vault | Plain file I/O with pathlib | No database, no embeddings |
| HTTP client | httpx (async) | Single dependency for all HTTP: search, scrape |

### Package

```
pydantic-ai-slim[openrouter]  # Slim build — only OpenRouter provider
httpx
trafilatura>=1.12,<3.0
aiogram>=3.10
apscheduler>=3.10
python-dotenv
structlog
pydantic-settings
```

Dev: `pytest`, `pytest-asyncio`, `pytest-mock`, `respx`

### Design Principles

- **Native tools over MCP servers.** MCP servers consume 30-50k tokens of context for tool definitions. Native Pydantic AI tool functions consume ~500 tokens total. Same functionality, 60x less context.
- **Single async process.** Telegram polling, APScheduler cron, and Pydantic AI agent share one event loop. No Docker, no microservices.
- **Purely usage-based APIs.** Every external service is free or pay-per-use. Zero fixed monthly costs beyond the Hetzner VPS.
- **Memory via preferences file.** A `preferences.md` markdown file is loaded into the system prompt on every run. Same pattern as `CLAUDE.md`. The owner edits it in Obsidian or tells the agent to update it via Telegram.
- **Two-pass daily pipeline.** Phase 1 generates the brief (research + write). Phase 2 reads the brief and updates entity files. Chained execution eliminates race conditions.

### Why httpx + trafilatura + Jina Reader

The original html2text approach converted the entire page DOM (nav, header, footer, menus) to markdown, wasting the 8000-char truncation budget on boilerplate. trafilatura uses content extraction heuristics to identify the main article/content area, producing dramatically cleaner output. It adds ~20+ transitive dependencies (including lxml) but the content quality improvement justifies the tradeoff.

For JS-rendered SPAs and bot-blocked sites where trafilatura returns thin content (<300 chars), the scraper falls back to Jina Reader API (`https://r.jina.ai/{url}`), which does server-side rendering. Jina is purely usage-based (~$0.02/M tokens, free tier ~20 RPM). The fallback is transparent — the tool signature is unchanged, and the return dict includes a `"source"` field for debugging.

---

## 3. Project Structure

```
bd-agent/
├── .env.example
├── .env                        # gitignored
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── README.md
├── CLAUDE.md
├── SPEC.md
├── src/
│   ├── __init__.py
│   ├── main.py                 # Entrypoint: wires scheduler + telegram + agent
│   ├── config.py               # Pydantic Settings for env vars
│   ├── agent.py                # Pydantic AI Agent definition + system prompt
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── research.py         # search_web, scrape_url
│   │   └── vault.py            # write_note, read_note, list_notes, list_all_entities, update_preferences
│   ├── telegram_bot.py         # aiogram dispatcher + message handlers
│   └── scheduler.py            # APScheduler setup + job definitions
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_tools_research.py
│   ├── test_tools_vault.py
│   ├── test_agent.py
│   ├── test_telegram.py
│   ├── test_scheduler.py
│   └── integration/            # Run by owner with real API keys
│       ├── conftest.py
│       ├── test_research_live.py
│       ├── test_agent_live.py
│       └── test_telegram_live.py
├── deploy/
│   ├── bd-agent.service        # systemd unit file
│   └── setup_server.sh         # Hetzner provisioning script
└── vault/
    ├── preferences.md          # Agent memory (checked into git)
    └── keypo-intel/
        ├── Daily/              # Daily intelligence briefs (YYYY-MM-DD.md)
        ├── Companies/          # Company entity files
        ├── People/             # People entity files
        ├── Topics/             # Topic entity files
        ├── Content Ideas/      # Content idea entity files
        └── Templates/          # Read-only entity templates
```

---

## 4. Configuration

Use `pydantic-settings` to load from `.env`. All external service keys are required. Everything else has sensible defaults.

### Required env vars
- `OPENROUTER_API_KEY`
- `BRAVE_API_KEY` — from brave.com/search/api/
- `TELEGRAM_BOT_TOKEN` — from @BotFather
- `TELEGRAM_CHAT_ID` — owner's personal chat ID (integer)

### Optional env vars with defaults
- `DEFAULT_MODEL` = `anthropic/claude-sonnet-4-5`
- `VAULT_PATH` = `./vault/keypo-intel`
- `BRIEFING_HOUR` / `BRIEFING_MINUTE` = 7:00
- `TIMEZONE` = `America/Los_Angeles`
- `SCRAPE_TIMEOUT` = 15 seconds
- `SCRAPE_MAX_CHARS` = 8000

---

## 5. Tool Contracts

Each tool is a native Pydantic AI tool function registered on the agent (7 total). Claude Code should implement these to satisfy the behavioral contracts below.

### 5.1 Research Tools (`src/tools/research.py`)

**`search_web`**
- Calls Brave Search API (`https://api.search.brave.com/res/v1/web/search`)
- Input: query string, optional count (default 5)
- Output: list of results, each with url, title, description
- Auth: `X-Subscription-Token` header with Brave API key
- Response path: `data["web"]["results"]`
- Should handle API errors gracefully

**`scrape_url`**
- Fetches a URL with httpx, extracts main content using trafilatura, with Jina Reader fallback
- Input: URL string
- Output: dict with `markdown`, `url`, `source` (`"trafilatura"`, `"jina"`, or `"error"`), and optionally `error`
- Must use a browser-like User-Agent header to avoid basic bot detection
- Must follow redirects
- Must check content-type is HTML (or XHTML) before attempting extraction — non-HTML returns error dict without triggering Jina
- Must truncate output to `SCRAPE_MAX_CHARS` to prevent context window blowup
- Check raw text length against `scrape_thin_threshold` (default 300) BEFORE truncating
- Errors should be returned as structured data (dict with `error` field), NOT raised as exceptions
- Jina Reader fallback triggers when: trafilatura returns thin content, trafilatura raises an exception, or the initial httpx fetch fails. Returns whichever result (Layer 1 or Jina) has more content
- trafilatura config: `include_links=True`, `include_tables=True`, `include_comments=False`, `output_format="markdown"`, `favor_recall=True`

### 5.2 Vault Tools (`src/tools/vault.py`)

**`write_note`**
- Writes a markdown file to vault/{folder}/{filename}
- Input: folder (must be in WRITABLE_FOLDERS), filename (auto-append .md), content string
- Path traversal guard: resolve path and check is_relative_to(vault_path)
- Templates/ is read-only — returns error if attempted

**`read_note`**
- Reads a markdown file from vault/{folder}/{filename}
- Works for all folders including Templates/
- Returns file content, truncated to READ_MAX_CHARS (50000)
- Returns clear message if file not found (don't raise)
- Path traversal guard

**`list_notes`**
- Lists .md filenames in vault/{folder}/
- Works for all readable folders

**`list_all_entities`**
- Lists all entity files across Companies/, People/, Topics/, Content Ideas/
- Returns dict with folder keys (lowercase, underscored) mapping to lists of filenames without .md extension
- Used for wikilink context before generating briefs

**`update_preferences`**
- Overwrites the preferences.md file with new content
- File lives at `vault_path.parent / "preferences.md"` (sibling to keypo-intel dir)

**`load_preferences`** (helper, not a tool)
- Reads preferences.md and returns its content as a string
- Called during system prompt construction, not by the agent directly
- Returns empty string if file doesn't exist

---

## 6. Agent Definition (`src/agent.py`)

### System Prompt

The system prompt has two parts concatenated at runtime:

1. **Base instructions** (hardcoded) — Tells the agent it works for Keypo, describes its two core jobs (daily brief + entity updates), vault structure, wikilink convention, CRM stages, and ad-hoc request handling.

2. **Owner preferences** (loaded from `preferences.md`) — Appended below the base instructions. Contains the owner's accumulated feedback on format, focus areas, and behavior.

### Critical: Callable System Prompt

Pass `_build_system_prompt` as a **function reference** to Pydantic AI's `system_prompt` parameter, NOT its return value. This ensures preferences.md is re-read on every `agent.run()` call, so preference changes take effect immediately.

### Tool Registration

Register all 7 tools on the agent: `search_web`, `scrape_url`, `write_note`, `read_note`, `list_notes`, `list_all_entities`, `update_preferences`.

---

## 7. Telegram Bot (`src/telegram_bot.py`)

- Use aiogram 3.x `Dispatcher` with a catch-all message handler
- **Auth check**: Only respond to messages from `TELEGRAM_CHAT_ID`. Reject all others.
- Route every message to `bd_agent.run(message.text)` and send back the output
- Telegram has a 4096 char limit per message — split long responses into chunks
- Provide a `send_briefing(text)` function for the scheduler to push messages to the owner
- Handle agent errors gracefully — send the error message to the owner, don't crash

---

## 8. Scheduler (`src/scheduler.py`)

- Use APScheduler's `AsyncIOScheduler` (shares event loop with aiogram)
- One cron job with two chained phases:

**Daily Marketing Brief** (weekdays at `BRIEFING_HOUR`:`BRIEFING_MINUTE`)
- **Phase 1**: Prompts the agent to generate an 8-section daily intelligence brief with folder-prefixed wikilinks. Writes to Daily/{date}.md. Sends brief via Telegram.
- **Phase 2**: Prompts the agent to read today's brief, extract wikilinked entities, and create/update entity files (Companies/, People/, Topics/, Content Ideas/) with YAML frontmatter and append-only logs. Sends summary via Telegram.
- Phase 2 only runs if Phase 1 succeeds (brief file exists).
- Each phase has independent error handling.

---

## 9. Main Entrypoint (`src/main.py`)

- Configure structlog
- Call `setup_scheduler()` and start it
- Start aiogram polling (this blocks until shutdown)
- On shutdown: stop scheduler, close bot session
- Run with `python -m src.main`

---

## 10. Build Phases & Test Gates

Build incrementally. Run the relevant tests after each phase. **Do not proceed to the next phase if tests fail.**

### Phase 1: Core Agent & Tools

Build: `config.py`, `tools/research.py`, `tools/vault.py`, `agent.py`

Seed file: Create `vault/preferences.md` with starter preferences covering 8-section briefing format, research focus areas, CRM stages, entity file standards, wikilink conventions, competitor list, and communication style.

**Test gate — run all Phase 1 tests before proceeding:**

| Test file | What to verify |
|-----------|---------------|
| `test_config.py` | Settings load from env vars. Missing required vars raise ValidationError. Defaults work. |
| `test_tools_research.py` | `search_web`: returns structured results from mocked Brave API response. Handles empty results. Respects count parameter. `scrape_url`: converts mocked HTML to markdown. Truncates long content. Returns error dict (not exception) on HTTP errors, non-HTML content-types, and connection failures. |
| `test_tools_vault.py` | `write_note`: creates file in correct folder, adds .md extension, rejects invalid folders/Templates/path traversal. `read_note`: reads content, returns message on missing file, works for Templates. `list_notes`: finds .md files. `list_all_entities`: scans entity folders, returns stems without .md. `update_preferences`/`load_preferences`: roundtrip works. |
| `test_agent.py` | Agent has all 7 tools registered. System prompt includes "Keypo". System prompt includes preferences.md content when file exists. System prompt works when preferences.md is missing. |

### Phase 2: Telegram Bot

Build: `telegram_bot.py`

**Test gate:**

| Test file | What to verify |
|-----------|---------------|
| `test_telegram.py` | Unauthorized chat IDs are rejected. Messages from authorized ID are routed to agent. Long responses are split at 4096 char boundary. Agent errors are caught and sent to user. |

### Phase 3: Scheduler

Build: `scheduler.py`

**Test gate:**

| Test file | What to verify |
|-----------|---------------|
| `test_scheduler.py` | Scheduler has one job (`daily_marketing_brief`). Job configured with correct hours from settings. Runs weekdays only. Two chained phases: brief → entity updates. Entity updates skipped if no brief file. |

### Phase 4: Main Entrypoint

Build: `main.py`

**Test gate:** Run the full offline test suite:
```bash
pytest tests/ -v --tb=short --ignore=tests/integration
```

### Phase 4.5: Integration Tests (Written by Claude Code, Run by Owner)

Write the integration test files in `tests/integration/`. **Do NOT run them** — they require real API keys the owner will provide later.

### Phase 5: Deployment Files

Create: `deploy/bd-agent.service` (systemd unit), `deploy/setup_server.sh` (Hetzner provisioning), `.env.example`

---

## 11. Testing Rules

### Offline tests (Phases 1-4)
- **No network calls.** Mock all HTTP with `respx`. Mock Telegram with `AsyncMock`.
- **Real filesystem for vault.** Use `pytest`'s `tmp_path` — catches real path and encoding bugs.
- **All env vars via fixtures.** Use `monkeypatch.setenv` in a shared `conftest.py` fixture.
- **Target <5 seconds** for the full suite.

### Integration tests (Phase 4.5)
- Auto-skip when API keys are missing or set to placeholder values.
- Hit real services — no mocking.
- Print diagnostic output (content lengths, etc).

### pyproject.toml
- `addopts = "--ignore=tests/integration"` so bare `pytest` never runs live tests
- `asyncio_mode = "auto"`

---

## 12. CLAUDE.md

Place in project root. Summarize:
- Project overview (one paragraph)
- Build order (phases 1-5 with test gates)
- Locked decisions table
- Key gotchas (callable system prompt, preferences.md location, vault_path default, folder-prefixed wikilinks, Templates read-only, entity append-only logs, path traversal guard, etc.)

---

## Appendix A: Model Downgrade Path

Start on `anthropic/claude-sonnet-4-5` for development. Once stable, downgrade to `google/gemini-2.5-flash` (~$1-3/month) by changing one line in `.env`. Fallback option: `openai/gpt-4o-mini`.

## Appendix B: Jina Reader Fallback (Implemented)

Jina Reader has been implemented as a fallback in `scrape_url`. When trafilatura returns thin content (<300 chars — increased from original 200 because trafilatura extracts less boilerplate than html2text), the scraper retries via `https://r.jina.ai/{url}`. The threshold increase avoids over-triggering on legitimate short pages. See Section 5.1 for the full tool contract. Settings: `JINA_API_KEY` (optional), `JINA_TIMEOUT` (default 30s), `JINA_FALLBACK_ENABLED` (default true).

## Appendix C: Vault Sync (Hetzner ↔ Local)

Options for syncing the vault between the Hetzner VPS and local Obsidian:
- **Git-based**: Auto-commit/push on server via cron, pull on Mac via Obsidian Git plugin. Gives version history.
- **Syncthing**: Real-time P2P sync. Simpler but no version history.

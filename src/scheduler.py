from datetime import datetime

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.agent import bd_agent, DEFAULT_MODEL
from src.config import get_settings
from src.telegram_bot import send_briefing

log = structlog.get_logger()

DAILY_BRIEF_TEMPLATE = """\
Today is {date}. Generate the daily Keypo marketing intelligence brief.

**Step 1 — Context:**
- Call list_all_entities() to see which companies/people/topics already have files (avoid repeating old leads).
- Read recent daily briefs with list_notes("Daily") and read_note("Daily", ...) for the most recent one to maintain continuity.

**Step 2 — Research:**
Run 15-20 searches across different angles. Use search_web for each, then scrape_url on the 5-8 most promising results.

**Recency:** For X/Twitter and Reddit searches, pass freshness="pw" (past week) to search_web. For industry/B2B searches, pass freshness="pm" (past month). Discard any X/Reddit engagement opportunities older than 7 days.

**Startup focus:** Include searches targeting early-stage companies alongside general industry queries.

Cover:
- "crypto wallet security" / "seed phrase recovery" / "Shamir Secret Sharing" (core topic)
- Twitter/X discussions: "seed phrase lost" OR "wallet recovery" OR "crypto backup"
- B2B signals: "crypto wallet partnership" / "wallet API integration" / "MPC wallet startup funding"
- **Startup-specific:** "crypto wallet startup funding 2026" / "seed phrase startup" / "wallet security Series A" / "web3 security seed round"
- Competitors: "Casa crypto" / "Ledger Recover" / "social recovery wallet"
- Apple ecosystem: "Apple Secure Enclave crypto" / "iPhone wallet security"
- Reddit: "reddit seed phrase" / "reddit crypto wallet security"
- Industry: "crypto custody news" / "web3 security startup"

**Step 3 — Write the brief:**
Write to Daily/{date}.md using write_note("Daily", "{date}.md", content).

Use this format (with YAML frontmatter):

---
type: daily-briefing
date: {date}
---

# Daily Briefing — {date}

## X Engagement Opportunities
5-8 tweets/threads worth engaging with. Only include tweets from the past 7 days — skip anything older. Include the account handle, a link, and a specific reply angle.

## Individual Leads
People who could be early adopters, advisors, or connectors. Prioritize people at startups and growth-stage companies. Avoid Fortune 500 executives unless there's a specific, actionable reason. Include context on why they're relevant.

## B2B Research & Partnership Leads
8-12 companies that could be partners or integration targets. Prioritize startups and growth-stage companies (Series A-C). Avoid well-known incumbents (Coinbase, Fireblocks, Ledger, Stripe, Meta, Citi) unless they have a specific new partnership program or API relevant to Keypo. Focus on companies small enough that a partnership conversation is realistic. For each: what they do, why they're relevant to Keypo, and a suggested next step. This is the priority section — make it the longest and most detailed.

## Competitor Watch
Activity from Casa, Ledger Recover, ZenGo, Vault12, social recovery wallets, and any new entrants. Track pricing changes, feature launches, funding, team changes.

## Keypo Mentions
Any mentions of Keypo, keypo.io, or our founders online. Track sentiment and reach.

## Reddit Opportunities
3-5 Reddit threads from the past 7 days where Keypo could add value. Skip older threads. Include the subreddit, thread title, link, and a brief suggested reply angle.

## Content Ideas
3-4 content pieces (tweets, threads, blog posts) based on today's research. Include the hook and key points.

## Strategic Ideas
2-3 higher-level observations: market shifts, partnership angles, positioning opportunities, timing considerations.

**Wikilink rules:**
- Use folder-prefixed wikilinks for ALL companies, people, and topics: [[Companies/Fireblocks]], [[People/Jane Doe]], [[Topics/MPC Wallets]]
- Entity files may not exist yet — that's fine, the entity update phase will create them
- Use clean names: alphanumeric + hyphens + spaces, no special characters

**Important:** Do NOT create or modify any entity files. Only write the Daily brief. Return the full brief text as your response.
"""

ENTITY_UPDATE_TEMPLATE = """\
Today is {date}. Read today's daily brief and create/update entity files in the vault.

**Step 1 — Read the brief:**
Call read_note("Daily", "{date}.md") to get today's briefing content.

**Step 2 — Discover existing entities:**
Call list_all_entities() to see which entity files already exist.

**Step 3 — Process each wikilinked entity:**

For every [[Companies/X]] wikilink in the brief:
- If X is in the existing companies list:
  1. read_note("Companies", "X.md") — read the ENTIRE current file
  2. Append a new log entry at the bottom of the Log section:
     ### {date} ([[Daily/{date}]])
     - <key finding or context from today's brief>
  3. Update last_updated: {date} in the YAML frontmatter
  4. Update stage if warranted (e.g., if outreach was sent, change new → outreach)
  5. write_note("Companies", "X.md", <COMPLETE file content>) — the full file, not just the new entry

- If X is NOT in the existing list (new entity):
  Create with this structure:
  ---
  type: company
  sector: "<inferred from brief>"
  status: prospect
  stage: new
  first_seen: {date}
  last_updated: {date}
  tags: [<relevant tags>]
  url: "<if found in brief>"
  contact_email: ""
  ---

  # X

  ## Overview
  <what they do, from the brief>

  ## Partnership Angle
  <how Keypo fits with their product>

  ## Key People
  <names and roles if mentioned>

  ## Log
  ### {date} ([[Daily/{date}]])
  - First identified. <context from brief>

For every [[People/X]] wikilink:
- Existing: read, append log entry with [[Daily/{date}]] backlink, update last_updated, write back
- New: create with frontmatter (type: person, company, role, status: active, first_seen, last_updated, tags, linkedin, email) + Context section + initial Log entry

For every [[Topics/X]] wikilink:
- Existing: read, append log entry, update last_updated, write back
- New: create with frontmatter (type: topic, status: active, first_seen, last_updated, tags) + Summary section + initial Log entry

For every [[Content Ideas/X]] wikilink:
- Existing: read, append log entry, update last_updated, write back
- New: create with frontmatter (type: content_idea, status: idea, format, topic, target_audience, first_seen, last_updated, tags) + Concept section + Key Points section + initial Log entry

**Critical rules:**
- ALWAYS read the entire file before updating — never overwrite without reading first
- NEVER delete or modify existing log entries — logs are append-only
- Write the COMPLETE file (all frontmatter + all existing body + new entry) when updating
- Use clean filenames: alphanumeric + hyphens + spaces, no special characters

**Return** a summary: "Vault updated: X companies (Y new, Z updated), W people, V topics, U content ideas"
"""

# Keep a static version for imports (e.g. test_briefing_verbose.py)
DAILY_BRIEFING_PROMPT = DAILY_BRIEF_TEMPLATE.format(date=datetime.now().strftime("%Y-%m-%d"))


async def daily_marketing_brief_job() -> None:
    """Full daily pipeline: brief generation → entity updates."""
    # Phase 1: Generate brief
    try:
        log.info("daily_brief_started")
        date = datetime.now().strftime("%Y-%m-%d")
        prompt = DAILY_BRIEF_TEMPLATE.format(date=date)
        result = await bd_agent.run(prompt, model=DEFAULT_MODEL)
        await send_briefing(result.output)
        log.info("daily_brief_completed")
    except Exception as e:
        log.error("daily_brief_failed", error=str(e))
        try:
            await send_briefing(f"Daily brief failed: {e}")
        except Exception:
            log.error("daily_brief_notification_failed")
        return  # Don't run entity updates if brief failed

    # Phase 2: Entity updates — has its own error handling
    await vault_entity_updates_job()


async def daily_brief_only_job() -> None:
    """Run Phase 1 only (brief generation), skip entity updates.
    Used by test scripts that don't need the full pipeline."""
    log.info("daily_brief_started")
    date = datetime.now().strftime("%Y-%m-%d")
    prompt = DAILY_BRIEF_TEMPLATE.format(date=date)
    result = await bd_agent.run(prompt, model=DEFAULT_MODEL)
    await send_briefing(result.output)
    log.info("daily_brief_completed")


async def vault_entity_updates_job() -> None:
    """Run Phase 2 only. Guards against missing daily brief."""
    try:
        log.info("entity_updates_started")
        date = datetime.now().strftime("%Y-%m-%d")
        settings = get_settings()
        brief_path = settings.vault_path / "Daily" / f"{date}.md"
        if not brief_path.exists():
            log.warning("entity_updates_skipped_no_brief", date=date)
            return
        prompt = ENTITY_UPDATE_TEMPLATE.format(date=date)
        result = await bd_agent.run(prompt, model=DEFAULT_MODEL)
        await send_briefing(result.output)
        log.info("entity_updates_completed")
    except Exception as e:
        log.error("entity_updates_failed", error=str(e))
        try:
            await send_briefing(f"Entity updates failed: {e}")
        except Exception:
            log.error("entity_updates_notification_failed")


def setup_scheduler() -> AsyncIOScheduler:
    settings = get_settings()
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    scheduler.add_job(
        daily_marketing_brief_job,
        CronTrigger(
            hour=settings.briefing_hour,
            minute=settings.briefing_minute,
            day_of_week="mon-fri",
            timezone=settings.timezone,
        ),
        id="daily_marketing_brief",
    )
    return scheduler

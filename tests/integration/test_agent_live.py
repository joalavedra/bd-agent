import pytest

from src.agent import bd_agent, DEFAULT_MODEL


async def test_agent_responds_to_message(live_settings):
    result = await bd_agent.run("Say hello in one sentence.", model=DEFAULT_MODEL)
    assert len(result.output) > 0
    print(f"Agent response: {result.output}")


async def test_agent_writes_vault_file(live_settings, tmp_path, monkeypatch):
    vault_path = tmp_path / "keypo-intel"
    for sub in ("Daily", "Companies", "People", "Topics", "Content Ideas", "Templates"):
        (vault_path / sub).mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("VAULT_PATH", str(vault_path))
    result = await bd_agent.run(
        "Write a test note to the Daily folder with filename 'integration-test.md' "
        "and content '# Test Briefing'.",
        model=DEFAULT_MODEL,
    )
    print(f"Agent response: {result.output}")
    # Check the file was created
    files = list((vault_path / "Daily").glob("*.md"))
    print(f"Files in vault: {[f.name for f in files]}")


async def test_agent_searches_and_scrapes(live_settings):
    result = await bd_agent.run(
        "Search for 'Fireblocks crypto custody' and scrape the first result. "
        "Give me a 2-sentence summary.",
        model=DEFAULT_MODEL,
    )
    assert len(result.output) > 0
    print(f"Agent response ({len(result.output)} chars): {result.output[:500]}")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.scheduler import (
    setup_scheduler,
    daily_marketing_brief_job,
    vault_entity_updates_job,
    DAILY_BRIEF_TEMPLATE,
    ENTITY_UPDATE_TEMPLATE,
)


def test_scheduler_has_one_job(env_vars):
    scheduler = setup_scheduler()
    jobs = {j.id: j for j in scheduler.get_jobs()}
    assert "daily_marketing_brief" in jobs
    assert len(jobs) == 1


def test_briefing_job_uses_correct_hour(env_vars, monkeypatch):
    monkeypatch.setenv("BRIEFING_HOUR", "9")
    monkeypatch.setenv("BRIEFING_MINUTE", "30")

    scheduler = setup_scheduler()
    job = next(j for j in scheduler.get_jobs() if j.id == "daily_marketing_brief")
    trigger = job.trigger
    trigger_str = str(trigger)
    assert "hour='9'" in trigger_str
    assert "minute='30'" in trigger_str


def test_briefing_runs_weekdays_only(env_vars):
    scheduler = setup_scheduler()
    job = next(j for j in scheduler.get_jobs() if j.id == "daily_marketing_brief")
    assert "mon-fri" in str(job.trigger)


async def test_daily_marketing_brief_job_calls_agent_and_sends(env_vars, tmp_path, monkeypatch):
    # Set up vault path so entity updates can check for brief file
    vault_path = tmp_path / "keypo-intel"
    (vault_path / "Daily").mkdir(parents=True)
    monkeypatch.setenv("VAULT_PATH", str(vault_path))

    mock_result_1 = MagicMock()
    mock_result_1.output = "Today's briefing summary"
    mock_result_2 = MagicMock()
    mock_result_2.output = "Vault updated: 3 companies"

    with (
        patch("src.scheduler.bd_agent") as mock_agent,
        patch("src.scheduler.send_briefing", new_callable=AsyncMock) as mock_send,
    ):
        mock_agent.run = AsyncMock(side_effect=[mock_result_1, mock_result_2])

        # Create the brief file so entity updates phase runs
        (vault_path / "Daily" / mock_result_1.output).touch()
        # Actually we need to simulate that write_note creates the file during phase 1
        # The brief file gets created by the agent during phase 1, so let's mock it
        import datetime
        date = datetime.datetime.now().strftime("%Y-%m-%d")
        (vault_path / "Daily" / f"{date}.md").write_text("brief content")

        await daily_marketing_brief_job()

    # Phase 1 + Phase 2 = 2 agent runs
    assert mock_agent.run.call_count == 2
    # Phase 1 briefing + Phase 2 entity summary = 2 send_briefing calls
    assert mock_send.call_count == 2
    mock_send.assert_any_call("Today's briefing summary")
    mock_send.assert_any_call("Vault updated: 3 companies")


async def test_daily_marketing_brief_job_notifies_on_error(env_vars):
    with (
        patch("src.scheduler.bd_agent") as mock_agent,
        patch("src.scheduler.send_briefing", new_callable=AsyncMock) as mock_send,
    ):
        mock_agent.run = AsyncMock(side_effect=RuntimeError("API down"))
        await daily_marketing_brief_job()

    mock_send.assert_called_once()
    assert "failed" in mock_send.call_args[0][0].lower()


async def test_daily_marketing_brief_skips_entities_on_brief_failure(env_vars):
    with (
        patch("src.scheduler.bd_agent") as mock_agent,
        patch("src.scheduler.send_briefing", new_callable=AsyncMock) as mock_send,
        patch("src.scheduler.vault_entity_updates_job", new_callable=AsyncMock) as mock_entity,
    ):
        mock_agent.run = AsyncMock(side_effect=RuntimeError("API down"))
        await daily_marketing_brief_job()

    # Entity updates should NOT be called if brief failed
    mock_entity.assert_not_called()


async def test_vault_entity_updates_skips_when_no_brief(env_vars, tmp_path, monkeypatch):
    vault_path = tmp_path / "keypo-intel"
    (vault_path / "Daily").mkdir(parents=True)
    monkeypatch.setenv("VAULT_PATH", str(vault_path))

    with (
        patch("src.scheduler.bd_agent") as mock_agent,
        patch("src.scheduler.send_briefing", new_callable=AsyncMock) as mock_send,
    ):
        await vault_entity_updates_job()

    # Agent should NOT be called if no brief file exists
    mock_agent.run.assert_not_called()


def test_templates_are_importable():
    assert "{date}" in DAILY_BRIEF_TEMPLATE
    assert "{date}" in ENTITY_UPDATE_TEMPLATE

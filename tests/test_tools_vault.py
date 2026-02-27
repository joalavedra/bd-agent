import pytest

from src.tools.vault import (
    write_note,
    read_note,
    list_notes,
    list_all_entities,
    update_preferences,
    load_preferences,
)


async def test_write_note_creates_file(settings):
    result = await write_note("Daily", "test-note.md", "# Hello", settings)
    assert "Daily/test-note.md" in result
    filepath = settings.vault_path / "Daily" / "test-note.md"
    assert filepath.exists()
    assert filepath.read_text() == "# Hello"


async def test_write_note_adds_md_extension(settings):
    await write_note("Daily", "test-note", "content", settings)
    assert (settings.vault_path / "Daily" / "test-note.md").exists()


async def test_write_note_invalid_folder(settings):
    result = await write_note("Invalid", "test.md", "content", settings)
    assert "Error" in result
    assert "invalid folder" in result.lower()


async def test_write_note_rejects_templates(settings):
    result = await write_note("Templates", "test.md", "content", settings)
    assert "Error" in result


async def test_write_note_rejects_path_traversal(settings):
    result = await write_note("Daily", "../../.env", "malicious", settings)
    assert "Error" in result
    # Verify the file was NOT created outside the vault
    assert not (settings.vault_path / "../../.env").exists()


async def test_read_note_returns_content(settings):
    (settings.vault_path / "Daily" / "note.md").write_text("# My Note")
    result = await read_note("Daily", "note.md", settings)
    assert result == "# My Note"


async def test_read_note_missing_file(settings):
    result = await read_note("Daily", "nonexistent.md", settings)
    assert "not found" in result.lower()


async def test_read_note_adds_md_extension(settings):
    (settings.vault_path / "Daily" / "note.md").write_text("content")
    result = await read_note("Daily", "note", settings)
    assert result == "content"


async def test_read_note_rejects_path_traversal(settings):
    result = await read_note("Daily", "../../.env", settings)
    assert "Error" in result


async def test_read_note_templates(settings):
    (settings.vault_path / "Templates" / "company.md").write_text("# Template")
    result = await read_note("Templates", "company.md", settings)
    assert result == "# Template"


async def test_list_notes_finds_md_files(settings):
    (settings.vault_path / "Daily" / "a.md").write_text("a")
    (settings.vault_path / "Daily" / "b.md").write_text("b")
    (settings.vault_path / "Daily" / "c.txt").write_text("c")

    notes = await list_notes("Daily", settings)
    assert notes == ["a.md", "b.md"]


async def test_list_notes_empty_folder(settings):
    notes = await list_notes("Daily", settings)
    assert notes == []


async def test_list_all_entities_scans_entity_folders(settings):
    (settings.vault_path / "Companies" / "Fireblocks.md").write_text("# Fireblocks")
    (settings.vault_path / "People" / "Jane Doe.md").write_text("# Jane")
    (settings.vault_path / "Topics" / "MPC Wallets.md").write_text("# MPC")
    (settings.vault_path / "Content Ideas" / "SSS Thread.md").write_text("# SSS")

    result = await list_all_entities(settings)
    assert "companies" in result
    assert "people" in result
    assert "topics" in result
    assert "content_ideas" in result
    assert "Fireblocks" in result["companies"]
    assert "Jane Doe" in result["people"]
    assert "MPC Wallets" in result["topics"]
    assert "SSS Thread" in result["content_ideas"]


async def test_list_all_entities_returns_stems(settings):
    (settings.vault_path / "Companies" / "Acme Corp.md").write_text("# Acme")
    result = await list_all_entities(settings)
    assert result["companies"] == ["Acme Corp"]
    # Should NOT include .md extension
    assert "Acme Corp.md" not in result["companies"]


async def test_list_all_entities_empty_dirs(settings):
    result = await list_all_entities(settings)
    assert result == {"companies": [], "people": [], "topics": [], "content_ideas": []}


async def test_write_read_roundtrip_with_frontmatter(settings):
    content = """---
type: company
sector: crypto
status: prospect
stage: new
first_seen: 2025-01-16
last_updated: 2025-01-16
tags: [custody, mpc]
url: "https://example.com"
contact_email: ""
---

# Example Corp

## Overview
A crypto company.

## Log
- 2025-01-16: First identified. ([[Daily/2025-01-16]])
"""
    await write_note("Companies", "Example Corp.md", content, settings)
    result = await read_note("Companies", "Example Corp.md", settings)
    assert result == content
    assert "type: company" in result
    assert "[[Daily/2025-01-16]]" in result


async def test_update_preferences_writes_file(settings):
    result = await update_preferences("# New Prefs", settings)
    assert "updated" in result.lower()
    prefs_path = settings.vault_path.parent / "preferences.md"
    assert prefs_path.read_text() == "# New Prefs"


async def test_load_preferences_reads_file(settings):
    prefs_path = settings.vault_path.parent / "preferences.md"
    prefs_path.write_text("# My Prefs")
    result = load_preferences(settings)
    assert result == "# My Prefs"


async def test_load_preferences_returns_empty_when_missing(settings):
    result = load_preferences(settings)
    assert result == ""


async def test_update_then_load_roundtrip(settings):
    await update_preferences("Focus on DeFi wallets", settings)
    result = load_preferences(settings)
    assert result == "Focus on DeFi wallets"

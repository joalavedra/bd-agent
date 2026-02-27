from src.agent import bd_agent, _build_system_prompt


EXPECTED_TOOLS = [
    "search_web",
    "scrape_url",
    "write_note",
    "read_note",
    "list_notes",
    "list_all_entities",
    "update_preferences",
]


def test_agent_has_all_tools():
    registered = list(bd_agent._function_toolset.tools.keys())
    for expected in EXPECTED_TOOLS:
        assert expected in registered, f"Missing tool: {expected}"


def test_agent_has_exactly_7_tools():
    assert len(bd_agent._function_toolset.tools) == 7


def test_system_prompt_includes_keypo(env_vars, tmp_path, monkeypatch):
    vault_path = tmp_path / "keypo-intel"
    vault_path.mkdir()
    monkeypatch.setenv("VAULT_PATH", str(vault_path))

    prompt = _build_system_prompt()
    assert "Keypo" in prompt


def test_system_prompt_includes_preferences(env_vars, tmp_path, monkeypatch):
    vault_path = tmp_path / "keypo-intel"
    vault_path.mkdir()
    monkeypatch.setenv("VAULT_PATH", str(vault_path))

    prefs_path = tmp_path / "preferences.md"
    prefs_path.write_text("Focus on MPC providers and hardware wallets")

    prompt = _build_system_prompt()
    assert "MPC providers" in prompt
    assert "hardware wallets" in prompt


def test_system_prompt_works_without_preferences(env_vars, tmp_path, monkeypatch):
    vault_path = tmp_path / "keypo-intel"
    vault_path.mkdir()
    monkeypatch.setenv("VAULT_PATH", str(vault_path))

    prompt = _build_system_prompt()
    assert "Keypo" in prompt
    assert "No preferences set yet" in prompt

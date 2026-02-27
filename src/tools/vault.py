from pathlib import Path

from src.config import Settings

READ_MAX_CHARS = 50_000

WRITABLE_FOLDERS = {"Daily", "Companies", "People", "Topics", "Content Ideas"}
READABLE_FOLDERS = WRITABLE_FOLDERS | {"Templates"}


async def write_note(folder: str, filename: str, content: str, settings: Settings) -> str:
    """Write a markdown file to vault/{folder}/{filename}.
    folder must be one of: Daily, Companies, People, Topics, Content Ideas.
    Templates/ is read-only."""
    if folder not in WRITABLE_FOLDERS:
        return f"Error: invalid folder '{folder}'. Must be one of: {sorted(WRITABLE_FOLDERS)}"
    if not filename.endswith(".md"):
        filename += ".md"
    target = (settings.vault_path / folder / filename).resolve()
    if not target.is_relative_to(settings.vault_path.resolve()):
        return "Error: invalid filename"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Wrote {folder}/{filename}"


async def read_note(folder: str, filename: str, settings: Settings) -> str:
    """Read a markdown file from vault/{folder}/{filename}.
    Works for all folders including Templates/."""
    if folder not in READABLE_FOLDERS:
        return f"Error: invalid folder '{folder}'. Must be one of: {sorted(READABLE_FOLDERS)}"
    if not filename.endswith(".md"):
        filename += ".md"
    target = (settings.vault_path / folder / filename).resolve()
    if not target.is_relative_to(settings.vault_path.resolve()):
        return "Error: invalid filename"
    if not target.exists():
        return f"File not found: {folder}/{filename}"
    text = target.read_text(encoding="utf-8")
    return text[:READ_MAX_CHARS]


async def list_notes(folder: str, settings: Settings) -> list[str]:
    """List .md filenames in vault/{folder}/."""
    if folder not in READABLE_FOLDERS:
        return []
    folder_path = settings.vault_path / folder
    if not folder_path.exists():
        return []
    return sorted(p.name for p in folder_path.glob("*.md"))


async def list_all_entities(settings: Settings) -> dict[str, list[str]]:
    """List all entity files across Companies/, People/, Topics/, Content Ideas/.
    Returns e.g. {'companies': ['Fireblocks', 'Vault12'], 'people': [...], ...}.
    Filenames returned WITHOUT .md extension for wikilink matching."""
    entity_folders = ["Companies", "People", "Topics", "Content Ideas"]
    result = {}
    for folder in entity_folders:
        key = folder.lower().replace(" ", "_")
        folder_path = settings.vault_path / folder
        if folder_path.exists():
            result[key] = sorted(p.stem for p in folder_path.glob("*.md"))
        else:
            result[key] = []
    return result


async def update_preferences(content: str, settings: Settings) -> str:
    """Overwrite the preferences.md file with new content."""
    prefs_path = Path(settings.vault_path).parent / "preferences.md"
    prefs_path.write_text(content, encoding="utf-8")
    return "Preferences updated."


def load_preferences(settings: Settings) -> str:
    """Read preferences.md content. Returns empty string if missing."""
    prefs_path = Path(settings.vault_path).parent / "preferences.md"
    if not prefs_path.exists():
        return ""
    return prefs_path.read_text(encoding="utf-8")

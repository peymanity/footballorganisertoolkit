"""Configuration management for Spond credentials and team settings."""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "footballorganisertoolkit"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    return json.loads(CONFIG_FILE.read_text())


def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2) + "\n")


def get_credentials() -> tuple[str, str]:
    """Return (username, password) from config, raising if not set."""
    config = load_config()
    username = config.get("spond_username")
    password = config.get("spond_password")
    if not username or not password:
        raise SystemExit(
            "Spond credentials not configured. Run: fot config --username <email> --password <password>"
        )
    return username, password


def get_group_id() -> str:
    """Return the configured group ID, raising if not set."""
    config = load_config()
    group_id = config.get("group_id")
    if not group_id:
        raise SystemExit(
            "No group configured. Run: fot groups  (to list groups)\n"
            "Then: fot config --group-id <id>"
        )
    return group_id

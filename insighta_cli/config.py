"""Persisted CLI configuration (~/.insighta/credentials.json)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_DEFAULT_API = "http://127.0.0.1:8000"
_DEFAULT_REDIRECT = "http://127.0.0.1:8765/callback"

CONFIG_DIR = Path.home() / ".insighta"
CREDENTIALS_PATH = CONFIG_DIR / "credentials.json"


def api_github_callback_url(api_base: str) -> str:
    """URL registered as the sole GitHub OAuth App callback (must match API + authorize request)."""
    return f"{api_base.rstrip('/')}/auth/github/callback"


def default_api_base_url() -> str:
    return os.environ.get("INSIGHTA_API_URL", _DEFAULT_API).strip().rstrip("/")


def default_oauth_redirect() -> str:
    """Local URL the API redirects to after /auth/github/callback for CLI flows. Must match API INSIGHTA_CLI_OAUTH_REDIRECT."""
    return os.environ.get("INSIGHTA_CLI_OAUTH_REDIRECT", _DEFAULT_REDIRECT).strip()


def default_github_client_id() -> str:
    return os.environ.get("INSIGHTA_GITHUB_CLIENT_ID", "").strip()


def load_credentials() -> dict[str, Any] | None:
    if not CREDENTIALS_PATH.is_file():
        return None
    try:
        raw = CREDENTIALS_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def save_credentials(data: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = CREDENTIALS_PATH
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def clear_credentials_file() -> None:
    try:
        CREDENTIALS_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def api_base_url_from_store_or_default(creds: dict[str, Any] | None) -> str:
    if creds:
        u = creds.get("api_base_url")
        if isinstance(u, str) and u.strip():
            return u.strip().rstrip("/")
    return default_api_base_url()

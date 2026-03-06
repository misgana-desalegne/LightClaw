from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _token_store_path() -> Path:
    configured = os.getenv("TOKEN_STORE_PATH", ".runtime_tokens.json")
    return Path(configured)


def load_tokens() -> dict[str, Any]:
    token_path = _token_store_path()
    if not token_path.exists():
        return {}
    try:
        return json.loads(token_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def get_token(key: str) -> str | None:
    tokens = load_tokens()
    value = tokens.get(key)
    if isinstance(value, str) and value:
        return value
    return None


def upsert_tokens(updates: dict[str, Any]) -> dict[str, Any]:
    token_path = _token_store_path()
    existing = load_tokens()
    existing.update({key: value for key, value in updates.items() if value is not None})
    token_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return existing

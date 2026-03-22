from __future__ import annotations

import os
from pathlib import Path


def _resolve_backend_root() -> Path:
    """Resolve backend project root, preferring BACKEND_ROOT or current cwd."""
    env_root = os.getenv("BACKEND_ROOT")
    if env_root:
        candidate = Path(env_root).expanduser().resolve()
        # Allow users to point at backend/app and normalize to backend root.
        if candidate.name == "app" and (candidate / "main.py").exists():
            candidate = candidate.parent
        return candidate

    cwd = Path.cwd().resolve()
    if cwd.name == "app" and (cwd / "main.py").exists():
        return cwd.parent
    if (cwd / "app").exists() and (cwd / "pyproject.toml").exists():
        return cwd

    # Fallback when imported from anywhere else.
    return Path(__file__).resolve().parents[2]


BACKEND_ROOT = _resolve_backend_root()
STORAGE_ROOT = BACKEND_ROOT / "storage"
RAW_UPLOADS_DIR = STORAGE_ROOT / "raw_uploads"
UPLOAD_HASH_DIR = STORAGE_ROOT / "upload_hash"
UPLOAD_HASH_INDEX_FILE = UPLOAD_HASH_DIR / "index.json"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

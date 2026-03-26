from __future__ import annotations

import os
from pathlib import Path


def _load_secrets_file(backend_root: Path) -> None:
    """Load KEY=VALUE lines from backend/.secrets into os.environ."""
    secrets_path = backend_root / ".secrets"
    if not secrets_path.exists() or not secrets_path.is_file():
        return

    for line in secrets_path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        if not key:
            continue
        # Do not override values that are already set by the environment.
        os.environ.setdefault(key, value.strip())

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


def _ensure_storage_dirs(storage_root: Path) -> None:
    for folder in ("raw_uploads", "upload_hash", "parsed_datasets", "job_artifacts"):
        (storage_root / folder).mkdir(parents=True, exist_ok=True)


BACKEND_ROOT = _resolve_backend_root()
_load_secrets_file(BACKEND_ROOT)
STORAGE_ROOT = BACKEND_ROOT / "storage"

_ensure_storage_dirs(STORAGE_ROOT)

RAW_UPLOADS_DIR = STORAGE_ROOT / "raw_uploads"
UPLOAD_HASH_DIR = STORAGE_ROOT / "upload_hash"
UPLOAD_HASH_INDEX_FILE = UPLOAD_HASH_DIR / "index.json"

# LLM runtime config
# For local Ollama-compatible routing, use:
#   LLM_BASE_URL=http://localhost:11434/v1
#   LLM_MODEL=ollama/llama3.2:3b
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "ollama/llama3.2:3b")
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
CODE_EXECUTOR_URL = os.getenv("CODE_EXECUTOR_URL", "http://localhost:8888/run")



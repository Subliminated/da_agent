from __future__ import annotations

import json
import os
import threading
from typing import Any


from app.core.config import STORAGE_ROOT, UPLOAD_HASH_DIR

_INDEX_LOCK = threading.Lock() 

_HASH_INDEX_FILE = str(UPLOAD_HASH_DIR / "by_hash.json")
_DATASET_INDEX_FILE = str(UPLOAD_HASH_DIR / "by_dataset_id.json")


_CACHE_BY_HASH: dict[str, dict[str, Any]] = {}
_CACHE_BY_DATASET_ID: dict[str, dict[str, Any]] = {}
_CACHE_STATE: tuple[float | None, float | None] | None = None

os.makedirs(str(UPLOAD_HASH_DIR), exist_ok=True)

def _normalize_meta(meta: Any, fallback_hash: str | None = None) -> dict[str, Any] | None:
    if not isinstance(meta, dict):
        return None

    normalized = dict(meta)
    dataset_id = normalized.get("dataset_id")
    if not isinstance(dataset_id, str) or not dataset_id.strip():
        return None

    normalized["dataset_id"] = dataset_id.strip()
    if fallback_hash and "file_hash" not in normalized:
        normalized["file_hash"] = fallback_hash

    source_label = normalized.get("source_label")
    if isinstance(source_label, str):
        source_label = source_label.strip()
        if source_label:
            normalized["source_label"] = source_label
        else:
            normalized.pop("source_label", None)
    else:
        normalized.pop("source_label", None)

    return normalized

def _safe_mtime(path: str) -> float | None:
    try:
        return os.path.getmtime(path)
    except FileNotFoundError:
        return None
    
def _load_json_map(path: str) -> dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _load_indexes_unlocked() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    global _CACHE_BY_HASH, _CACHE_BY_DATASET_ID, _CACHE_STATE

    state = (_safe_mtime(_HASH_INDEX_FILE), _safe_mtime(_DATASET_INDEX_FILE))
    if _CACHE_STATE == state:
        return _CACHE_BY_HASH, _CACHE_BY_DATASET_ID

    raw_by_hash = _load_json_map(_HASH_INDEX_FILE)
    raw_by_dataset_id = _load_json_map(_DATASET_INDEX_FILE)

    by_hash: dict[str, dict[str, Any]] = {}
    by_dataset_id: dict[str, dict[str, Any]] = {}

    for file_hash, meta in raw_by_hash.items():
        if not isinstance(file_hash, str):
            continue
        normalized = _normalize_meta(meta, fallback_hash=file_hash)
        if not normalized:
            continue
        by_hash[file_hash] = normalized
        by_dataset_id[normalized["dataset_id"]] = normalized

    for dataset_id, meta in raw_by_dataset_id.items():
        if not isinstance(dataset_id, str):
            continue
        normalized = _normalize_meta(meta)
        if not normalized:
            continue
        normalized["dataset_id"] = dataset_id
        by_dataset_id[dataset_id] = normalized
        file_hash = normalized.get("file_hash")
        if isinstance(file_hash, str) and file_hash:
            by_hash[file_hash] = normalized

    _CACHE_BY_HASH = by_hash
    _CACHE_BY_DATASET_ID = by_dataset_id
    _CACHE_STATE = state
    return by_hash, by_dataset_id


def _save_indexes_unlocked(by_hash: dict[str, dict[str, Any]], by_dataset_id: dict[str, dict[str, Any]]) -> None:
    global _CACHE_BY_HASH, _CACHE_BY_DATASET_ID, _CACHE_STATE

    hash_tmp = f"{_HASH_INDEX_FILE}.tmp"
    dataset_tmp = f"{_DATASET_INDEX_FILE}.tmp"

    with open(hash_tmp, "w", encoding="utf-8") as f:
        json.dump(by_hash, f, ensure_ascii=False, indent=2)
    with open(dataset_tmp, "w", encoding="utf-8") as f:
        json.dump(by_dataset_id, f, ensure_ascii=False, indent=2)

    os.replace(hash_tmp, _HASH_INDEX_FILE)
    os.replace(dataset_tmp, _DATASET_INDEX_FILE)

    _CACHE_BY_HASH = by_hash
    _CACHE_BY_DATASET_ID = by_dataset_id
    _CACHE_STATE = (_safe_mtime(_HASH_INDEX_FILE), _safe_mtime(_DATASET_INDEX_FILE))


def get_by_hash(file_hash: str) -> dict[str, Any] | None:
    with _INDEX_LOCK:
        by_hash, _ = _load_indexes_unlocked()
        record = by_hash.get(file_hash)
        return dict(record) if isinstance(record, dict) else None


def get_by_dataset_id(dataset_id: str) -> dict[str, Any] | None:
    with _INDEX_LOCK:
        _, by_dataset_id = _load_indexes_unlocked()
        record = by_dataset_id.get(dataset_id)
        return dict(record) if isinstance(record, dict) else None


def get_by_source_label(source_label: str) -> dict[str, Any] | None:
    lookup = source_label.strip().lower()
    if not lookup:
        return None

    with _INDEX_LOCK:
        _, by_dataset_id = _load_indexes_unlocked()

        candidates: list[dict[str, Any]] = []
        for record in by_dataset_id.values():
            if not isinstance(record, dict):
                continue
            current_label = record.get("source_label")
            if isinstance(current_label, str) and current_label.strip().lower() == lookup:
                candidates.append(record)

        if not candidates:
            return None

        def _created_at_key(item: dict[str, Any]) -> float:
            value = item.get("created_at")
            if isinstance(value, (int, float)):
                return float(value)
            return 0.0

        selected = max(candidates, key=_created_at_key)
        return dict(selected)


def list_records() -> list[dict[str, Any]]:
    with _INDEX_LOCK:
        _, by_dataset_id = _load_indexes_unlocked()
        records: list[dict[str, Any]] = []
        for record in by_dataset_id.values():
            if not isinstance(record, dict):
                continue

            stored_path = record.get("stored_path")
            if not isinstance(stored_path, str) or not stored_path.strip():
                continue

            absolute_path = STORAGE_ROOT / stored_path
            if not absolute_path.exists() or not absolute_path.is_file():
                continue

            records.append(dict(record))

    def _created_at_key(item: dict[str, Any]) -> float:
        value = item.get("created_at")
        if isinstance(value, (int, float)):
            return float(value)
        return 0.0

    records.sort(key=_created_at_key, reverse=True)
    return records


def upsert_record(file_hash: str, meta: dict[str, Any]) -> None:
    normalized = _normalize_meta(meta, fallback_hash=file_hash)
    if normalized is None:
        raise ValueError("meta must include a non-empty dataset_id")

    normalized["file_hash"] = file_hash
    dataset_id = normalized["dataset_id"]

    with _INDEX_LOCK:
        by_hash, by_dataset_id = _load_indexes_unlocked()
        by_hash[file_hash] = normalized
        by_dataset_id[dataset_id] = normalized
        _save_indexes_unlocked(by_hash, by_dataset_id)

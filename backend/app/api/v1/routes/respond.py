import json

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Any, NoReturn, cast

from app.core.config import STORAGE_ROOT
from app.services.llm import LLMClient
from app.services.storage import get_by_dataset_id, get_by_source_label


router = APIRouter()

class AnalysisJobRequest(BaseModel):
    dataset_selector: str | None = None
    dataset_id: str | None = None
    user_prompt: str
    memory: list[dict[str, str]] = Field(default_factory=list)


def structured_error(status_code: int, code: str, message: str, details: dict | None = None) -> NoReturn:
    payload = {"error": {"code": code, "message": message, "details": None}}
    if details is not None:
        payload["error"]["details"] = details
    raise HTTPException(status_code=status_code, detail=payload)


def _resolve_record(selector: str) -> dict[str, Any] | None:
    record = get_by_dataset_id(selector)
    if record:
        return record
    return get_by_source_label(selector)


def _resolve_stored_path(record: dict[str, Any]) -> str | None:
    if not record:
        return None

    stored_path = record.get("stored_path")
    if not isinstance(stored_path, str) or not stored_path:
        return None

    return str(STORAGE_ROOT / stored_path)

def _format_prompt(dataset_id: str, stored_path: str, user_prompt: str) -> str:
    return (
        "You are analyzing an uploaded dataset. "
        #f"dataset_id={dataset_id}; stored_path={stored_path}. "
        f"User request: {user_prompt}"
    )

@router.post("/analysis/jobs")
async def respond_job(payload: AnalysisJobRequest) -> dict:
    dataset_selector = (payload.dataset_selector or payload.dataset_id or "").strip()
    user_prompt = payload.user_prompt.strip()

    if not dataset_selector or not user_prompt:
        structured_error(
            status.HTTP_400_BAD_REQUEST,
            "MISSING_FIELDS",
            "dataset_selector (or dataset_id) and user_prompt are required",
        )

    resolved_record = _resolve_record(dataset_selector)
    if not isinstance(resolved_record, dict):
        structured_error(
            status.HTTP_404_NOT_FOUND,
            "DATASET_NOT_FOUND",
            "dataset selector not found",
            {"dataset_selector": dataset_selector},
        )

    record = cast(dict[str, Any], resolved_record)
    stored_path = _resolve_stored_path(record)
    if stored_path is None:
        structured_error(
            status.HTTP_404_NOT_FOUND,
            "DATASET_NOT_FOUND",
            "dataset selector not found",
            {"dataset_selector": dataset_selector},
        )

    resolved_dataset_id = record.get("dataset_id")
    dataset_id = str(resolved_dataset_id) if isinstance(resolved_dataset_id, str) else ""
    if not dataset_id:
        structured_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INDEX_DATA_INVALID",
            "dataset record is missing dataset_id",
        )

    safe_memory: list[dict[str, str]] = []
    for message in payload.memory:
        role = message.get("role")
        content = message.get("content")
        if role not in {"user", "assistant", "system"}:
            continue
        if not isinstance(content, str) or not content.strip():
            continue
        safe_memory.append({"role": role, "content": content.strip()})

    try:
        llm = LLMClient(memory=safe_memory)
        # prompt manage stage 
        prompt = _format_prompt(dataset_id, stored_path, user_prompt)
        llm_response = llm.chat_with_usage(prompt)

        raw_reply = llm_response.get("reply")
        parsed_reply = llm_response.get("reply_json")

        if not isinstance(parsed_reply, dict):
            if isinstance(raw_reply, str):
                try:
                    maybe = json.loads(raw_reply)
                    parsed_reply = maybe if isinstance(maybe, dict) else {"message": raw_reply}
                except json.JSONDecodeError:
                    parsed_reply = {"message": raw_reply}
            else:
                parsed_reply = {"message": ""}

        llm_response["reply_json"] = parsed_reply
    except ValueError as exc:
        structured_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "LLM_CONFIG_ERROR",
            str(exc),
        )
    except Exception as exc:  # pragma: no cover - defensive path for provider/network failures
        structured_error(
            status.HTTP_502_BAD_GATEWAY,
            "LLM_CALL_FAILED",
            "failed to generate response from llm",
            {"reason": str(exc)},
        )
    return {
        "status": "accepted",
        "dataset_id": dataset_id,
        "source_label": record.get("source_label"),
        "result": llm_response.get("reply_json", {"message": ""}),
        "usage": llm_response.get("usage", {}),
    }


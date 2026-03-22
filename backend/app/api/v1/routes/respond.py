from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
import glob
import os
from typing import NoReturn

from ....core.config import RAW_UPLOADS_DIR
from ....services.llm import LLMClient

router = APIRouter()
RAW_DIR = str(RAW_UPLOADS_DIR)


class AnalysisJobRequest(BaseModel):
    dataset_id: str
    user_prompt: str


def structured_error(status_code: int, code: str, message: str, details: dict | None = None) -> NoReturn:
    payload = {"error": {"code": code, "message": message, "details": None}}
    if details is not None:
        payload["error"]["details"] = details
    raise HTTPException(status_code=status_code, detail=payload)


def _validate_dataset_id(dataset_id: str) -> str | None:
    matches = glob.glob(os.path.join(RAW_DIR, f"{dataset_id}__*"))
    return matches[0] if matches else None


def _format_prompt(dataset_id: str, stored_path: str, user_prompt: str) -> str:
    return (
        "You are analyzing an uploaded dataset. "
        f"dataset_id={dataset_id}; stored_path={stored_path}. "
        f"User request: {user_prompt}"
    )


@router.post("/analysis/jobs")
async def respond_job(payload: AnalysisJobRequest) -> dict:
    dataset_id = payload.dataset_id.strip()
    user_prompt = payload.user_prompt.strip()

    if not dataset_id or not user_prompt:
        structured_error(
            status.HTTP_400_BAD_REQUEST,
            "MISSING_FIELDS",
            "dataset_id and user_prompt are required",
        )

    stored_path = _validate_dataset_id(dataset_id)
    if stored_path is None:
        structured_error(
            status.HTTP_404_NOT_FOUND,
            "DATASET_NOT_FOUND",
            "dataset_id not found",
            {"dataset_id": dataset_id},
        )

    try:
        llm = LLMClient(memory=[])
        prompt = _format_prompt(dataset_id, stored_path, user_prompt)
        llm_response = llm.chat(prompt)
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
        "result": llm_response,
    }


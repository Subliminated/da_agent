"""
Provides an abstraction layer for client.py
This layer is intended to process the actual requst of the user without impacting the llm client directly (it may be used for other taskks)
"""
from __future__ import annotations

import json
import logging
from typing import Any
import os
import requests

from app.core.config import BACKEND_ROOT, CODE_EXECUTOR_URL
from app.services.llm.client import LLMClient
from app.services.storage import get_by_dataset_id

MAX_CALLS = 3
CONTAINER_DATA_ROOT = "/data"
LOGGER = logging.getLogger(__name__)

_STRUCTURED_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "analysis_response",
        "schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "code": {"type": "string"},
                "call_tool": {"type": "boolean"},
            },
            "required": ["message", "code", "call_tool"],
            "additionalProperties": False,
        },
        "strict": True,
    },
}

SYS_PROMPT_FILE = os.path.join(BACKEND_ROOT,"app","domain","prompts","system.md")
try:
    with open(SYS_PROMPT_FILE, "r", encoding="utf-8") as f:
        system_prompt = f.read()
except Exception:
    system_prompt = "You are a helpful data analyst assistant."

# Structure to coerce the failed json response into json from raw message
def _coerce_structured_json(llm_response) -> dict[str,Any]:
    raw_llm_response = llm_response.get("reply")
    parsed_llm_response = llm_response.get("reply_json")

    if not isinstance(parsed_llm_response, dict):
        if isinstance(raw_llm_response, str):
            try:
                maybe = json.loads(raw_llm_response)
                parsed_llm_response = maybe if isinstance(maybe, dict) else {"message": raw_llm_response}
            except json.JSONDecodeError:
                parsed_llm_response = {"message": raw_llm_response}
        else:
            parsed_llm_response = {"message": ""}

    message = parsed_llm_response.get("message", "")
    code = parsed_llm_response.get("code", "")
    call_tool = parsed_llm_response.get("call_tool", False)

    if not isinstance(message, str):
        message = str(message)
    if not isinstance(code, str):
        code = str(code)
    if not isinstance(call_tool, bool):
        call_tool = str(call_tool).strip().lower() in {"1", "true", "yes"}

    parsed_llm_response = {
        "message": message,
        "code": code,
        "call_tool": call_tool,
    }

    llm_response["reply_json"] = parsed_llm_response
    return llm_response

def _resolve_stored_path_from_dataset_id(dataset_id: str) -> str | None:
    if not dataset_id:
        return None

    record = get_by_dataset_id(dataset_id)
    if not isinstance(record, dict):
        return None

    stored_path = record.get("stored_path")
    if not isinstance(stored_path, str) or not stored_path.strip():
        return None

    return stored_path.strip()

def _to_container_data_path(stored_path: str) -> str:
    normalized = stored_path.strip().lstrip("/")
    return f"{CONTAINER_DATA_ROOT}/{normalized}"


def _format_prompt(dataset_id: str, user_prompt: str) -> str:
    stored_path = _resolve_stored_path_from_dataset_id(dataset_id)

    if stored_path:
        container_stored_path = _to_container_data_path(stored_path)
        data_context = (
            f"dataset_id={dataset_id}; "
            f"stored_path={container_stored_path}; "
            "storage_access=read_only"
        )
    else:
        data_context = (
            f"dataset_id={dataset_id}; "
            "stored_path=unknown"
        )

    return (
        "You are analyzing an uploaded dataset. "
        f"{data_context}. "
        "Each code execution runs in a fresh Python process, so always load the dataset from stored_path and define df in every code snippet. "
        "If you generate code, read the file from stored_path and do not write back to that path. "
        f"User request: {user_prompt}"
    )


def _execution_succeeded(result: dict[str, Any]) -> bool:
    if not result.get("ok"):
        return False

    returncode = result.get("returncode")
    stderr = str(result.get("stderr") or "").strip()
    return returncode == 0 and not stderr


def _build_executable_code(code: str, stored_path: str | None) -> str:
    snippet = str(code or "").strip()
    if not stored_path:
        return snippet

    # Guardrail: each run is stateless, so ensure df is defined if model forgot to load it.
    if "pd.read_csv" in snippet and stored_path in snippet:
        return snippet

    bootstrap = (
        "import pandas as pd\n"
        f"df = pd.read_csv({stored_path!r})\n"
    )
    return f"{bootstrap}{snippet}" if snippet else bootstrap

def code_executor(code: str) -> dict[str, Any]:
    try:
        response = requests.post(CODE_EXECUTOR_URL, json={"code": code}, timeout=35)
    except requests.RequestException as exc:
        return {
            "ok": False,
            "stdout": "",
            "stderr": "",
            "returncode": None,
            "status_code": None,
            "error": str(exc),
        }
    if response.ok:
        result = response.json()
        LOGGER.info("Code execution finished", extra={"returncode": result.get("returncode")})
        return {
            "ok": True,
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "returncode": result.get("returncode"),
            "status_code": response.status_code,
            "error": "",
        }
    return {
        "ok": False,
        "stdout": "",
        "stderr": response.text,
        "returncode": None,
        "status_code": response.status_code,
        "error": f"HTTP {response.status_code}",
    }


def _is_placeholder_message(message: str) -> bool:
    lowered = message.strip().lower()
    if not lowered:
        return True
    return "has requested" in lowered or lowered.startswith("the user has requested")


def _default_reply_json() -> dict[str, Any]:
    return {"message": "", "code": "", "call_tool": False}


def _extract_reply_json(payload: dict[str, Any]) -> dict[str, Any]:
    candidate = payload.get("reply_json", _default_reply_json())
    if not isinstance(candidate, dict):
        return _default_reply_json()
    return {
        "message": str(candidate.get("message", "") or ""),
        "code": str(candidate.get("code", "") or ""),
        "call_tool": bool(candidate.get("call_tool", False)),
    }


def respond_to_job(
    prompt: str,
    memory: list[dict[str, str]],
    dataset_id: str
    ) -> dict:
    """The actual logic layer that manages the response callback logic assuming validations complete
    Enforces Json output
    """
    supervisor = LLMClient(memory=memory)
    user_prompt = prompt
    planning_prompt = _format_prompt(dataset_id, user_prompt)
    stored_path = _resolve_stored_path_from_dataset_id(dataset_id)
    container_stored_path = _to_container_data_path(stored_path) if stored_path else None
    
    # Step 1: Plan
    supervisor_response = supervisor.chat_with_usage(
        planning_prompt,
        response_schema=_STRUCTURED_RESPONSE_SCHEMA,
        system_prompt=system_prompt,
    )

    json_response = _extract_reply_json(supervisor_response)
    code_execution_response: dict[str, Any] = {
        "ok": False,
        "stdout": "",
        "stderr": "",
        "returncode": None,
        "status_code": None,
        "error": "",
    }

    # Step 2 + 3: Execute and repair
    for _ in range(MAX_CALLS):
        if not json_response.get("call_tool") or not json_response.get("code"):
            break

        executable_code = _build_executable_code(str(json_response.get("code")), container_stored_path)
        code_execution_response = code_executor(executable_code)

        if _execution_succeeded(code_execution_response):
            break

        repair_prompt = f"""
        Error from triggered code execution call:
        {code_execution_response.get("stderr")}

        Your original code:
        {json_response.get("code")}

        Dataset file path:
        {container_stored_path}

        Produce corrected python code and set call_tool=true.
        """
        supervisor_response = supervisor.chat_with_usage(
            repair_prompt,
            response_schema=_STRUCTURED_RESPONSE_SCHEMA,
            system_prompt=system_prompt,
        )
        json_response = _extract_reply_json(supervisor_response)

    # Step 4: Finalize
    if _execution_succeeded(code_execution_response):
        finalize_prompt = f"""
        Original question from user:
        {user_prompt}

        Results from triggered code execution call:
        {code_execution_response.get("stdout")}

        Return final answer using the actual execution output above.
        Do not paraphrase the request. Include the concrete result in message.
        Set call_tool to false and code to an empty string.
        """
        supervisor_response = supervisor.chat_with_usage(
            finalize_prompt,
            response_schema=_STRUCTURED_RESPONSE_SCHEMA,
            system_prompt=system_prompt,
        )
        json_response = _extract_reply_json(supervisor_response)

        stdout_text = str(code_execution_response.get("stdout") or "").strip()
        current_message = str(json_response.get("message") or "")
        if stdout_text and _is_placeholder_message(current_message):
            json_response.update({"message": stdout_text, "code": "", "call_tool": False})
            supervisor_response["reply_json"] = json_response
    elif code_execution_response.get("stderr"):
        fallback_message = str(code_execution_response.get("stderr") or "Execution failed").strip()
        supervisor_response["reply_json"] = {
            "message": fallback_message,
            "code": "",
            "call_tool": False,
        }

    # Update the final supervisor response
    supervisor_response = _coerce_structured_json(supervisor_response) 
    
    return supervisor_response

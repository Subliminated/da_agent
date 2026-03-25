"""
Provides an abstraction layer for client.py
This layer is intended to process the actual requst of the user without impacting the llm client directly (it may be used for other taskks)
"""
from __future__ import annotations

import json
from typing import Any
import os
import requests

from app.core.config import BACKEND_ROOT
from app.services.llm.client import LLMClient
from app.services.storage import get_by_dataset_id

MAX_CALLS = 3
CONTAINER_DATA_ROOT = "/data"

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
                "answered": {"type": "boolean"},
            },
            "required": ["message", "code", "call_tool", "answered"],
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
    answered = parsed_llm_response.get("answered", False)

    if not isinstance(message, str):
        message = str(message)
    if not isinstance(code, str):
        code = str(code)
    if not isinstance(call_tool, bool):
        call_tool = str(call_tool).strip().lower() in {"1", "true", "yes"}
    if not isinstance(answered, bool):
        answered = str(answered).strip().lower() in {"1", "true", "yes"}

    parsed_llm_response = {
        "message": message,
        "code": code,
        "call_tool": call_tool,
        "answered": answered,
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
        "If you generate code, read the file from stored_path and do not write back to that path. "
        f"User request: {user_prompt}"
    )

def code_executor(code: str) -> str:
    try:
        response = requests.post("http://localhost:8888/run", json={"code": code}, timeout=35)
    except requests.RequestException as exc:
        output_str = f"[ERROR] failed to call code executor: {exc}"
        print(output_str)
        return output_str

    if response.ok:
        result = response.json()
        output_str = (
            "=== STDOUT ===\n"
            + result.get("stdout", "").strip()
            + "\n=== STDERR ===\n"
            + result.get("stderr", "").strip()
        )
        print(output_str)
        return output_str
    else:
        output_str = f"[ERROR] {response.status_code}: {response.text}"
        print(output_str)
        return output_str


def respond_to_job(
    prompt: str,
    memory: list[dict[str, str]],
    dataset_id: str
    ) -> dict:
    """The actual logic layer that manages the response callback logic assuming validations complete
    Enforces Json output
    """
    #supervisor = LLMClient(memory=memory) # Reads intent and rephrases into python question
    supervisor = LLMClient()
    # System prompt:
    #SYS_PROMPT_FILE

    # Gather stats for LLM context to be ingested into system prompt

    user_prompt = prompt
    prompt = _format_prompt(dataset_id, user_prompt)
    
    # First call to determine the intent
    supervisor_response = supervisor.chat_with_usage(
        prompt,
        response_schema=_STRUCTURED_RESPONSE_SCHEMA,
        system_prompt=system_prompt,
    )

    json_response: dict[str,Any] = supervisor_response.get(
        "reply_json",
        {"message": "", "code": "", "call_tool": False, "answered": False},
    )
    print(f"\033[94m{json_response}\033[0m")

    # Tool Call loop to answer question 3 tries
    count = 0

    while not json_response.get("answered", False) and count < MAX_CALLS:
        # Check if call tool is empty and code provided.
        if json_response.get("code") and not json_response.get("call_tool"):
            json_response.update({"call_tool":True})
        if not json_response.get("code") and json_response.get("call_tool"):
            json_response.update({"call_tool":False})

        if json_response.get("call_tool",None):
            python_code_to_execute = str(json_response.get("code"))
            code_execution_response = code_executor(python_code_to_execute)

            # Fire the code to the code execution environment
            temp_prompt = f"""
            Results from triggered code execution call:
            {code_execution_response}

            Original question from user:
            {user_prompt}

            Dataset context:
            {prompt}

            If the code has an error, attemp to address it first, before making a response
            """
            # Run tool call (with memory)
            supervisor_response = supervisor.chat_with_usage(
                temp_prompt,
                response_schema=_STRUCTURED_RESPONSE_SCHEMA,
                system_prompt=system_prompt,
            )
            json_response = supervisor_response.get(
                "reply_json",
                {"message": "", "code": "", "call_tool": False, "answered": False},
            )
            print(f"\033[94m{json_response}\033[0m")

        else:
            # No tool requested, force completion to avoid spinning.
            json_response.update({"answered": True})
            supervisor_response["reply_json"] = json_response

        # Evaluate tool call result: if the result is good, respond to user. 
        count += 1
        if count == MAX_CALLS:
            json_response.update({"answered": True})
            supervisor_response["reply_json"] = json_response
    
    #Update the final supervisor response
    supervisor_response = _coerce_structured_json(supervisor_response) 
    
    return supervisor_response

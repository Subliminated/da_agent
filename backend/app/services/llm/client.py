from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from litellm import completion

from app.core.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

_STRUCTURED_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "json_schema",
    "json_schema": {
        "name": "analysis_response",
        "schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "highlights": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "confidence": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                },
            },
            "required": ["message"],
            "additionalProperties": True,
        },
        "strict": True,
    },
}

@dataclass
class LLMClient:
    """LiteLLM wrapper with optional conversational memory."""

    memory: list[dict[str, str]] = field(default_factory=list)
    model: str = LLM_MODEL
    base_url: str = LLM_BASE_URL
    api_key: str | None = LLM_API_KEY

    def __post_init__(self) -> None:
        if not self.model:
            raise ValueError("LLM_MODEL is not set")

    def _coerce_structured_json(self, raw_text: str) -> dict[str, Any]:
        if not raw_text:
            return {"message": ""}

        stripped = raw_text.strip()
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                message = parsed.get("message")
                if not isinstance(message, str):
                    parsed["message"] = stripped
                return parsed
        except json.JSONDecodeError:
            pass

        return {"message": stripped}

    def chat(self, prompt: str, system_prompt: str = "You are a helpful data analyst assistant.") -> str:
        return self.chat_with_usage(prompt, system_prompt=system_prompt)["reply"]

    def chat_with_usage(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful data analyst assistant.",
    ) -> dict[str, Any]:
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}, *self.memory]
        messages.append({"role": "user", "content": prompt})

        try:
            response = completion(
                model=self.model,
                messages=messages,
                base_url=self.base_url,
                api_key=self.api_key,
                temperature=0.0,
                response_format=_STRUCTURED_RESPONSE_SCHEMA,
            )
        except Exception:
            # Some providers/models do not support JSON schema response format.
            response = completion(
                model=self.model,
                messages=messages,
                base_url=self.base_url,
                api_key=self.api_key,
                temperature=0.0,
            )

        parsed: Any = response
        text = parsed.choices[0].message.content or ""
        structured_reply = self._coerce_structured_json(text)
        assistant_reply = json.dumps(structured_reply, ensure_ascii=False)

        usage_raw = getattr(parsed, "usage", None)
        prompt_tokens = int(getattr(usage_raw, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage_raw, "completion_tokens", 0) or 0)
        total_tokens = int(getattr(usage_raw, "total_tokens", prompt_tokens + completion_tokens) or 0)

        self.memory.append({"role": "user", "content": prompt})
        self.memory.append({"role": "assistant", "content": assistant_reply})
        print(structured_reply )
        return {
            "reply": assistant_reply,
            "reply_json": structured_reply,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
        }

if __name__ == "__main__":
    query = "what is the molecular formula for acryniltrile"
    client = LLMClient()
    print(client.chat(prompt = query))
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from litellm import completion
from pydantic import BaseModel
import os

from app.core.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

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

    def chat(self, prompt: str) -> str:
        return self.chat_with_usage(prompt)["reply"]

    def chat_with_usage(
        self,
        prompt: str,
        response_schema: dict[str,Any] | None = None,
        system_prompt: str = "You are a helpful data analyst assistant.",
        ctx: str = ""
    ) -> dict[str, Any]:

        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}, *self.memory]
        messages.append({"role": "user", "content": prompt})

        response: Any | None = None

        if response_schema is None:
            response = completion(
                model=self.model,
                messages=messages,
                base_url=self.base_url,
                api_key=self.api_key,
                temperature=0.0,
            )
        else:
            last_error: Exception | None = None
            for attempt in range(1, 4):
                try:
                    response = completion(
                        model=self.model,
                        messages=messages,
                        base_url=self.base_url,
                        api_key=self.api_key,
                        temperature=0.0,
                        response_format=response_schema,
                    )
                    print(f"RESPONSE IS JSON ENFORCED (attempt {attempt}/3)")
                    break
                except Exception as exc:
                    last_error = exc
                    print(f"Schema-enforced call failed (attempt {attempt}/3): {exc}")
                    if attempt == 3:
                        raise RuntimeError(
                            "Failed to get schema-enforced response after 3 attempts"
                        ) from last_error

        if response is None:
            raise RuntimeError("LLM completion returned no response")

        parsed: Any = response
        text = parsed.choices[0].message.content or ""
        structured_reply = self._coerce_structured_json(text) #In json compatible form
        
        if structured_reply.get("confidence",None):
            print(f"Confidence score found {structured_reply}")
        else:
            print("No confidence score")
        
        assistant_reply = json.dumps(structured_reply.get("message",""), ensure_ascii=False)

        usage_raw = getattr(parsed, "usage", None)
        prompt_tokens = int(getattr(usage_raw, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage_raw, "completion_tokens", 0) or 0)
        total_tokens = int(getattr(usage_raw, "total_tokens", prompt_tokens + completion_tokens) or 0)

        self.memory.append({"role": "user", "content": prompt})
        self.memory.append({"role": "assistant", "content": assistant_reply})
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
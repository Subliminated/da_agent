from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from litellm import completion

from ...core.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


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

    def chat(self, prompt: str, system_prompt: str = "You are a helpful data analyst assistant.") -> str:
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}, *self.memory]
        messages.append({"role": "user", "content": prompt})

        response = completion(
            model=self.model,
            messages=messages,
            base_url=self.base_url,
            api_key=self.api_key,
            temperature=0.0,
        )

        parsed: Any = response
        text = parsed.choices[0].message.content or ""
        assistant_reply = text.strip()

        self.memory.append({"role": "user", "content": prompt})
        self.memory.append({"role": "assistant", "content": assistant_reply})

        return assistant_reply
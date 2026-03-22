from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from ...core.config import OPENAI_API_KEY, OPENAI_MODEL


@dataclass
class LLMClient:
    """Minimal OpenAI client wrapper with optional conversational memory."""

    memory: list[dict[str, str]] = field(default_factory=list)
    model: str = OPENAI_MODEL
    api_key: str = OPENAI_API_KEY

    def __post_init__(self) -> None:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        self._client = OpenAI(api_key=self.api_key)

    def chat(self, prompt: str, system_prompt: str = "You are a helpful data analyst assistant.") -> str:
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}, *self.memory]
        messages.append({"role": "user", "content": prompt})

        completion = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
        )

        text = completion.choices[0].message.content or ""
        assistant_reply = text.strip()

        self.memory.append({"role": "user", "content": prompt})
        self.memory.append({"role": "assistant", "content": assistant_reply})

        return assistant_reply

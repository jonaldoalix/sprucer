from __future__ import annotations

from typing import Any, Protocol

import httpx


class LlmAdapter(Protocol):
    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int = 1800,
        temperature: float = 0.35,
    ) -> str: ...


class OpenAICompatLlm:
    def __init__(self, *, base_url: str, api_key: str, default_model: str) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.default_model = default_model or "qwen-coder"

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int = 1800,
        temperature: float = 0.35,
    ) -> str:
        if not self.base_url:
            raise RuntimeError("SPRUCER_LLM_URL is not configured")
        if not self.api_key:
            raise RuntimeError("SPRUCER_LLM_API_KEY is not configured")
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=300.0, trust_env=False) as client:
            res = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if res.status_code >= 400:
                raise RuntimeError(f"LLM HTTP {res.status_code}: {res.text[:400]}")
            data = res.json()
        try:
            return data["choices"][0]["message"]["content"]
        except Exception as exc:
            raise RuntimeError(f"LLM unexpected response: {str(data)[:300]}") from exc


class MockLlm:
    """Deterministic LLM for tests — no network."""

    def __init__(self, reply: str | None = None) -> None:
        self.reply = reply
        self.calls: list[list[dict[str, str]]] = []

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int = 1800,
        temperature: float = 0.35,
    ) -> str:
        self.calls.append(messages)
        if self.reply is not None:
            return self.reply
        return (
            "## cover\n\nI am writing from grounded fixture facts only.\n\n"
            "## Emphasis\n\n- metric-pr-speed\n"
        )

from __future__ import annotations

import json
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
        # Local Ollama (esp. CPU) can exceed 5m on cold multi-artifact drafts.
        async with httpx.AsyncClient(timeout=900.0, trust_env=False) as client:
            try:
                res = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            except httpx.TimeoutException as exc:
                raise RuntimeError(
                    "LLM timed out. Try fewer artifact types, a faster model, or raise the LLM timeout."
                ) from exc
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
        types: list[str] = []
        cite_ids: list[str] = []
        for msg in messages:
            if msg.get("role") != "user":
                continue
            raw = msg.get("content") or ""
            try:
                payload = json.loads(raw)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            if payload.get("artifactTypes"):
                types = [str(t) for t in payload["artifactTypes"]]
            catalog = payload.get("interviewCiteCatalog") or []
            if isinstance(catalog, list):
                for row in catalog:
                    if isinstance(row, dict) and row.get("id"):
                        cite_ids.append(str(row["id"]))
        if not types:
            types = ["cover", "email"]
        while len(cite_ids) < 3:
            cite_ids.append(f"fixture-cite-{len(cite_ids)+1}")
        c0, c1, c2 = cite_ids[0], cite_ids[1], cite_ids[2]
        sections: list[str] = []
        for t in types:
            if t == "cover":
                sections.append(
                    "## Cover Letter\n\nI am writing from grounded fixture facts only.\n"
                )
            elif t == "email":
                sections.append(
                    "## Email\n\nSubject: Application\n\nHello,\n\nI am writing about this role.\n\nThanks\n"
                )
            elif t == "resume":
                sections.append(
                    "## Resume\n\n### Experience\n- Built grounded fixture systems end to end.\n"
                )
            elif t == "interview":
                sections.append(
                    "## Interview Prep\n\n"
                    "### Likely questions\n"
                    "1. How do you ship reliable platforms?\n"
                    f"   - Answer with: Lead with ownership of client platforms. Cite: `{c0}`\n"
                    "2. Tell me about a production estate you ran.\n"
                    f"   - Answer with: Point to a concrete metric from the vault. Cite: `{c1}`\n"
                    "3. How do you handle operational ownership?\n"
                    f"   - Answer with: Ground the answer in a real role or project. Cite: `{c2}`\n"
                    "### Refresh from your knowledge bank\n"
                    f"- `{c0}` — vault item\n"
                    f"- `{c1}` — vault item\n"
                    f"- `{c2}` — vault item\n"
                    "### Watch-outs\n"
                    "- Never invent unverified percentage metrics\n"
                )
            elif t == "linkedin":
                sections.append(
                    "## LinkedIn DM\n\n"
                    "Hi team — I build client platforms end to end and saw your role. "
                    "Would you be open to a short chat about fit?\n\n"
                    "Jonaldo\n"
                )
            else:
                label = t.replace("custom:", "").replace("-", " ").title()
                sections.append(f"## {label}\n\nGrounded custom draft from fixture facts.\n")
        return "\n".join(sections)

"""Thin async streaming client for OpenRouter (OpenAI-compatible SSE).

Yields ("text", chunk) events as tokens arrive and one ("usage", {...}) event at
the end. Network is mocked in tests; this module never holds business logic.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

_URL = "https://openrouter.ai/api/v1/chat/completions"


async def stream_completion(
    *,
    messages: list[dict[str, str]],
    model: str,
    api_key: str,
    temperature: float,
) -> AsyncIterator[tuple[str, object]]:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://hongyuane.github.io/ourcafe-guardrails",
        "X-Title": "OurCafe Guardrails Demo",
    }
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream("POST", _URL, json=payload, headers=headers) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]" or not data:
                    continue
                obj = json.loads(data)
                choices = obj.get("choices") or []
                if choices:
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yield "text", content
                if obj.get("usage"):
                    u = obj["usage"]
                    yield "usage", {
                        "prompt_tokens": u.get("prompt_tokens", 0),
                        "completion_tokens": u.get("completion_tokens", 0),
                    }

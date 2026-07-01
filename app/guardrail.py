"""/guardrail-chat: a server-side-guarded, streaming LLM proxy.

The system prompt and model are enforced here and never exposed to clients. A
tiered per-IP round limiter guards cost; the finite OpenRouter balance is the hard
ceiling (provider errors degrade to a friendly 'capacity' signal).
"""
from __future__ import annotations

import json
import os
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .config import Settings
from .guardrail_prompt import build_messages
from .llm_client import stream_completion
from .ratelimit import get_rate_limiter

router = APIRouter()
settings = Settings()
rate_limiter = get_rate_limiter(settings)


def _dumps(obj: object) -> str:
    """Compact JSON (no spaces) so the SSE wire format is stable and small."""
    return json.dumps(obj, separators=(",", ":"))


class Turn(BaseModel):
    role: str
    content: str


class GuardrailChatRequest(BaseModel):
    history: list[Turn] = Field(default_factory=list)
    user_input: str
    attack_type: str | None = None
    new_round: bool = False


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


@router.post("/guardrail-chat")
async def guardrail_chat(req: GuardrailChatRequest, request: Request):
    if req.new_round:
        decision = rate_limiter.start_round(_client_ip(request))
        if not decision.allowed:
            return JSONResponse(status_code=429,
                                content={"error": "rate_limited", "retry_after": decision.retry_after})

    api_key = os.getenv("OPENROUTER_API_KEY", "")  # read at request time (test-friendly)
    if not api_key:
        return JSONResponse(status_code=503, content={"error": "capacity"})

    # turn budget: history holds prior (user, assistant) pairs → count assistant turns used
    used = sum(1 for t in req.history if t.role == "assistant")
    remaining = max(0, settings.turns_per_round - used - 1)
    must_conclude = remaining <= 0
    messages = build_messages(
        history=[t.model_dump() for t in req.history],
        user_input=req.user_input,
        remaining_turns=remaining,
        must_conclude=must_conclude,
    )

    async def event_stream():
        start = time.monotonic()
        ttft_ms = None
        usage = {"prompt_tokens": 0, "completion_tokens": 0}
        try:
            async for kind, payload in stream_completion(
                messages=messages, model=settings.model,
                api_key=api_key, temperature=settings.temperature,
            ):
                if kind == "text":
                    if ttft_ms is None:
                        ttft_ms = int((time.monotonic() - start) * 1000)
                    yield f"data: {_dumps({'t': payload})}\n\n"
                elif kind == "usage":
                    usage = payload
        except Exception:  # provider/balance failure → graceful capacity signal
            yield f"data: {_dumps({'done': True, 'capacity': True})}\n\n"
            return
        final = {"done": True, "conclude": must_conclude, "ttft_ms": ttft_ms or 0, **usage}
        yield f"data: {_dumps(final)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

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


# Lucia ends EVERY reply with exactly one silent control tag: [[END]] when the interaction is
# finished, [[MORE]] when it should continue. Always-present tags are followed far more
# reliably by small models than a single conditional marker. We strip whichever tag from the
# client-visible text; [[END]] additionally ends the round early (a natural end, before the
# hard cap). The tags are chosen to be vanishingly unlikely in real café dialogue.
END_TAG = "[[END]]"
CONTINUE_TAG = "[[MORE]]"
_TAGS = (END_TAG, CONTINUE_TAG)
_MAX_TAG = max(len(t) for t in _TAGS)


def _scan_tags(buffer: str) -> tuple[str, str, bool]:
    """Process a growing buffer for the control tags.

    Returns ``(emit, held, ended)``:
    - ``emit``: text that is safe to stream to the client now (never contains a tag).
    - ``held``: a suffix kept back because it might still grow into a tag.
    - ``ended``: True if a complete [[END]] tag was seen.
    """
    for tag in _TAGS:
        i = buffer.find(tag)
        if i != -1:
            return buffer[:i], buffer[i + len(tag):], tag == END_TAG
    # No complete tag — hold back the longest suffix that could be a partial tag.
    for k in range(min(_MAX_TAG - 1, len(buffer)), 0, -1):
        suffix = buffer[-k:]
        if any(t.startswith(suffix) for t in _TAGS):
            return buffer[:-k], suffix, False
    return buffer, "", False


def _is_partial_tag(text: str) -> bool:
    return bool(text) and any(t.startswith(text) for t in _TAGS)


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

    # Turn budget: count Lucia's prior replies; the reply we're about to generate is next.
    # Soft-wrap from soft_wrap_turn onward; hard-end (and signal the client to terminate the
    # round) at hard_end_turn — regardless of whether the model plays along.
    used = sum(1 for t in req.history if t.role == "assistant")
    reply_num = used + 1
    if reply_num >= settings.hard_end_turn:
        wrap = "hard"
    elif reply_num >= settings.soft_wrap_turn:
        wrap = "soft"
    else:
        wrap = "none"
    conclude = reply_num >= settings.hard_end_turn
    messages = build_messages(
        history=[t.model_dump() for t in req.history],
        user_input=req.user_input,
        wrap=wrap,
    )

    async def event_stream():
        start = time.monotonic()
        ttft_ms = None
        usage = {"prompt_tokens": 0, "completion_tokens": 0}
        pending = ""          # held-back tail that might be a partial SENTINEL
        model_ended = False   # Lucia emitted the end-marker → natural end
        try:
            async for kind, payload in stream_completion(
                messages=messages, model=settings.model,
                api_key=api_key, temperature=settings.temperature,
            ):
                if kind == "usage":
                    usage = payload
                    continue
                if model_ended:
                    continue  # ignore anything after the end tag
                if ttft_ms is None:
                    ttft_ms = int((time.monotonic() - start) * 1000)
                pending += payload
                emit, pending, ended = _scan_tags(pending)
                if emit:
                    yield f"data: {_dumps({'t': emit})}\n\n"
                if ended:
                    model_ended = True
            # Flush any leftover tail, unless it's a dangling partial tag (drop that).
            if pending and not model_ended and not _is_partial_tag(pending):
                yield f"data: {_dumps({'t': pending})}\n\n"
        except Exception:  # provider/balance failure → graceful capacity signal
            yield f"data: {_dumps({'done': True, 'capacity': True})}\n\n"
            return
        final = {"done": True, "conclude": conclude or model_ended, "ttft_ms": ttft_ms or 0, **usage}
        yield f"data: {_dumps(final)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

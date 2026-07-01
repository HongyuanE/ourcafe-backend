"""Compose the guarded chat messages sent to the model.

The system prompt lives here (server-side only) and is never exposed to clients.
The final user message wraps the visitor's raw input in a turn envelope so the
model honours the per-round turn budget.
"""
from __future__ import annotations

from pathlib import Path

_PROMPT_PATH = Path(__file__).parent / "prompts" / "npc_system_prompt_en.md"
SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8").strip()


def build_messages(
    *,
    history: list[dict[str, str]],
    user_input: str,
    remaining_turns: int,
    must_conclude: bool,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    envelope = (
        "=== Café conversation turn ===\n"
        f"Player says: {user_input}\n"
        f"Remaining turns: {remaining_turns}\n"
    )
    if must_conclude:
        envelope += "This is the final turn — give a warm closing line.\n"
    envelope += "Reply only as Kathrine's next line."
    messages.append({"role": "user", "content": envelope})
    return messages

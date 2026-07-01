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
    wrap: str = "none",
) -> list[dict[str, str]]:
    """Compose system + history + the current turn.

    ``wrap`` controls how hard we nudge Lucia to end the conversation:
    - "none": normal turn.
    - "soft": begin wrapping up (kicks in from the soft-wrap reply onward).
    - "hard": this must be the final line (the hard-end reply).
    """
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    envelope = (
        "=== Café conversation turn ===\n"
        f"Player says: {user_input}\n"
    )
    if wrap == "soft":
        envelope += (
            "(You've been chatting for a little while — gently start wrapping up: finish the "
            "order and move toward a warm goodbye rather than opening new topics.)\n"
        )
    elif wrap == "hard":
        envelope += (
            "(This must be your final line. Give a warm goodbye and end the conversation now — "
            "do not ask another question or invite more chat.)\n"
        )
    envelope += "Reply only as Lucia's next line."
    messages.append({"role": "user", "content": envelope})
    return messages

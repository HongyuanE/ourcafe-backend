"""Runtime configuration for the guardrail proxy.

All tunables come from environment variables with safe defaults, so the same
code runs locally (via a .env) and in Lambda (env injected by Terraform).
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw not in (None, "") else default


@dataclass(frozen=True)
class Settings:
    model: str = "google/gemini-3.1-flash-lite"
    temperature: float = 0.1
    free_rounds: int = 0
    max_rounds_per_day: int = 0
    round_cooldown_seconds: int = 0
    turns_per_round: int = 0
    soft_wrap_turn: int = 0
    hard_end_turn: int = 0
    allowed_origin: str = ""
    openrouter_api_key: str = ""
    ip_hash_salt: str = ""

    def __init__(self) -> None:
        object.__setattr__(
            self, "model", os.getenv("GUARDRAIL_MODEL", "google/gemini-3.1-flash-lite")
        )
        object.__setattr__(self, "temperature", float(os.getenv("GUARDRAIL_TEMPERATURE", "0.1")))
        object.__setattr__(self, "free_rounds", _int("FREE_ROUNDS", 5))
        object.__setattr__(self, "max_rounds_per_day", _int("MAX_ROUNDS_PER_DAY", 10))
        object.__setattr__(self, "round_cooldown_seconds", _int("ROUND_COOLDOWN_SECONDS", 30))
        object.__setattr__(self, "turns_per_round", _int("TURNS_PER_ROUND", 5))
        # From the Nth reply, gently wrap up; at the Mth reply, force a hard goodbye.
        object.__setattr__(self, "soft_wrap_turn", _int("SOFT_WRAP_TURN", 5))
        object.__setattr__(self, "hard_end_turn", _int("HARD_END_TURN", 7))
        object.__setattr__(self, "allowed_origin", os.getenv("GUARDRAIL_ALLOWED_ORIGIN", "http://localhost:5173"))
        object.__setattr__(self, "openrouter_api_key", os.getenv("OPENROUTER_API_KEY", ""))
        object.__setattr__(self, "ip_hash_salt", os.getenv("IP_HASH_SALT", "dev-salt"))

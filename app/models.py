"""Data models for the Ourcafe leaderboard.

A "score" is the total cash a player has earned at the end of Ourcafe's
three-day run. Players are identified by a client-generated PlayerId (a GUID
the game stores locally) — there is no login.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ScoreSubmission(BaseModel):
    """Payload the game POSTs when a run finishes."""

    player_id: str = Field(min_length=1, max_length=64, description="Client-generated GUID")
    player_name: str = Field(default="Anonymous", max_length=32)
    score: int = Field(ge=0, description="Total cash earned across the 3-day run")


class ScoreEntry(BaseModel):
    """A stored leaderboard entry (a submission plus when it was recorded)."""

    player_id: str
    player_name: str
    score: int
    created_at: str  # ISO-8601 UTC

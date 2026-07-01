"""Ourcafe leaderboard API.

Backend for the leaderboard in *Ourcafe* (a Unity café game). Players submit the
total cash earned after the three-day run; the API stores it and serves the
ranking. Designed to run serverless (AWS Lambda + DynamoDB) so it costs nothing
while idle.
"""
from __future__ import annotations

import os
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings as _Settings
from .guardrail import router as guardrail_router
from .models import ScoreEntry, ScoreSubmission
from .storage import get_storage

app = FastAPI(title="ourcafe-backend", version="0.1.0")

_settings = _Settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[_settings.allowed_origin, "http://localhost:5173"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)
app.include_router(guardrail_router)

GIT_SHA = os.getenv("GIT_SHA", "dev")
storage = get_storage()


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "ourcafe-backend", "commit": GIT_SHA}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/scores", status_code=201)
def submit_score(submission: ScoreSubmission) -> ScoreEntry:
    """Record a finished run's cash total."""
    entry = ScoreEntry(
        player_id=submission.player_id,
        player_name=submission.player_name,
        score=submission.score,
        created_at=datetime.now(UTC).isoformat(),
    )
    storage.add_score(entry)
    return entry


@app.get("/leaderboard")
def leaderboard(limit: int = 20) -> dict[str, list[ScoreEntry]]:
    """Return the top scores, highest first."""
    limit = max(1, min(limit, 100))
    return {"leaderboard": storage.top_scores(limit)}


# AWS Lambda entry point. Mangum adapts the ASGI app to the Lambda runtime so the
# exact same FastAPI code runs locally (uvicorn) and in the cloud (Lambda).
try:
    from mangum import Mangum

    handler = Mangum(app)
except ImportError:  # pragma: no cover - mangum only needed in the Lambda image
    handler = None

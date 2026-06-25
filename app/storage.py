"""Storage backends for leaderboard entries.

The app talks to an abstract ``Storage`` interface so the business logic never
depends on where data lives. Local development and tests use a fast in-memory
store; the deployed service uses DynamoDB. The backend is chosen at runtime via
the ``STORAGE_BACKEND`` environment variable.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod

from .models import ScoreEntry


class Storage(ABC):
    @abstractmethod
    def add_score(self, entry: ScoreEntry) -> None: ...

    @abstractmethod
    def top_scores(self, limit: int = 20) -> list[ScoreEntry]: ...


class InMemoryStorage(Storage):
    """Non-persistent store for local dev and tests."""

    def __init__(self) -> None:
        self._entries: list[ScoreEntry] = []

    def add_score(self, entry: ScoreEntry) -> None:
        self._entries.append(entry)

    def top_scores(self, limit: int = 20) -> list[ScoreEntry]:
        ranked = sorted(self._entries, key=lambda e: e.score, reverse=True)
        return ranked[:limit]

    def clear(self) -> None:
        self._entries.clear()


class DynamoDBStorage(Storage):
    """Durable store backed by a single DynamoDB table.

    Modelling: all scores share one partition (``pk = "SCORE"``) with a sort key
    that is the zero-padded score, so a descending Query returns the top N in a
    single, cheap request — the classic small-leaderboard pattern.

    NOTE: exercised against real DynamoDB on deploy; unit tests use the in-memory
    backend, so treat first-deploy as the integration test for this class.
    """

    def __init__(self, table_name: str) -> None:
        import boto3  # imported lazily so local/test runs need no AWS deps

        self._table = boto3.resource("dynamodb").Table(table_name)

    def add_score(self, entry: ScoreEntry) -> None:
        self._table.put_item(
            Item={
                "pk": "SCORE",
                # zero-pad so lexical sort == numeric sort; suffix keeps ties unique
                "sk": f"{entry.score:012d}#{entry.created_at}#{entry.player_id}",
                "player_id": entry.player_id,
                "player_name": entry.player_name,
                "score": entry.score,
                "created_at": entry.created_at,
            }
        )

    def top_scores(self, limit: int = 20) -> list[ScoreEntry]:
        from boto3.dynamodb.conditions import Key

        response = self._table.query(
            KeyConditionExpression=Key("pk").eq("SCORE"),
            ScanIndexForward=False,  # descending → highest scores first
            Limit=limit,
        )
        return [
            ScoreEntry(
                player_id=item["player_id"],
                player_name=item["player_name"],
                score=int(item["score"]),
                created_at=item["created_at"],
            )
            for item in response.get("Items", [])
        ]


def get_storage() -> Storage:
    """Select the storage backend from the environment."""
    backend = os.getenv("STORAGE_BACKEND", "memory").lower()
    if backend == "dynamodb":
        return DynamoDBStorage(os.environ["DYNAMODB_TABLE"])
    return InMemoryStorage()

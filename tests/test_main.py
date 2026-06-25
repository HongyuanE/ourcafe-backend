import pytest
from fastapi.testclient import TestClient

from app.main import app, storage

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_storage():
    # Tests share the module-level in-memory store; reset before each one.
    if hasattr(storage, "clear"):
        storage.clear()
    yield


def test_health_is_ok():
    assert client.get("/health").json() == {"status": "ok"}


def test_submit_then_appears_on_leaderboard():
    response = client.post(
        "/scores", json={"player_id": "p1", "player_name": "Ann", "score": 150}
    )
    assert response.status_code == 201
    assert response.json()["score"] == 150

    board = client.get("/leaderboard").json()["leaderboard"]
    assert len(board) == 1
    assert board[0]["player_name"] == "Ann"
    assert "created_at" in board[0]


def test_leaderboard_is_sorted_highest_first_and_respects_limit():
    client.post("/scores", json={"player_id": "p1", "score": 100})
    client.post("/scores", json={"player_id": "p2", "score": 300})
    client.post("/scores", json={"player_id": "p3", "score": 200})

    board = client.get("/leaderboard?limit=2").json()["leaderboard"]
    assert [e["score"] for e in board] == [300, 200]


def test_negative_score_is_rejected():
    response = client.post("/scores", json={"player_id": "p1", "score": -5})
    assert response.status_code == 422


def test_player_name_defaults_to_anonymous():
    client.post("/scores", json={"player_id": "p9", "score": 10})
    board = client.get("/leaderboard").json()["leaderboard"]
    assert board[0]["player_name"] == "Anonymous"

import json
from fastapi.testclient import TestClient


def _mock_stream(monkeypatch):
    async def fake_stream(**kwargs):
        yield "text", "Hi "
        yield "text", "there"
        yield "usage", {"prompt_tokens": 30, "completion_tokens": 5}
    monkeypatch.setattr("app.guardrail.stream_completion", fake_stream)


def test_happy_path_streams_text_and_final_usage(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    _mock_stream(monkeypatch)
    from app.main import app
    client = TestClient(app)
    r = client.post("/guardrail-chat", json={"history": [], "user_input": "hi", "new_round": True})
    assert r.status_code == 200
    body = r.text
    assert '{"t":"Hi "}' in body
    assert '{"t":"there"}' in body
    assert '"done":true' in body
    assert '"completion_tokens":5' in body


def test_round_limit_denies_after_cap(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    _mock_stream(monkeypatch)
    import app.guardrail as g
    from app.ratelimit import InMemoryRateLimiter
    # swap in a tiny limiter directly — robust against import-time env capture
    monkeypatch.setattr(g, "rate_limiter",
                        InMemoryRateLimiter(free_rounds=1, max_rounds_per_day=1, cooldown_seconds=30))
    from app.main import app
    client = TestClient(app)
    ok = client.post("/guardrail-chat", json={"history": [], "user_input": "hi", "new_round": True})
    assert ok.status_code == 200
    denied = client.post("/guardrail-chat", json={"history": [], "user_input": "hi", "new_round": True})
    assert denied.status_code == 429
    assert denied.json()["error"] == "rate_limited"

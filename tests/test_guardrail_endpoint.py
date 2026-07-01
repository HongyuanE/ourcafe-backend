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


def test_end_tag_is_stripped_and_concludes(monkeypatch):
    """The [[END]] tag (even split across chunks) is removed from the visible text and
    flips conclude=true so the round ends naturally."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")

    async def fake_stream(**kwargs):
        yield "text", "Enjoy your coffee! "
        yield "text", "[["          # tag split across chunks
        yield "text", "END]]"
        yield "usage", {"prompt_tokens": 20, "completion_tokens": 4}
    monkeypatch.setattr("app.guardrail.stream_completion", fake_stream)

    from app.main import app
    client = TestClient(app)
    r = client.post("/guardrail-chat", json={"history": [], "user_input": "thanks", "new_round": True})
    body = r.text
    assert "Enjoy your coffee!" in body
    assert "[[" not in body                 # tag fully stripped, no leak
    assert '"conclude":true' in body


def test_more_tag_is_stripped_without_concluding(monkeypatch):
    """The [[MORE]] tag is removed from the visible text but does NOT conclude the round."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")

    async def fake_stream(**kwargs):
        yield "text", "Coming right up! Anything else? "
        yield "text", "[[MORE]]"
        yield "usage", {"prompt_tokens": 15, "completion_tokens": 6}
    monkeypatch.setattr("app.guardrail.stream_completion", fake_stream)

    from app.main import app
    client = TestClient(app)
    r = client.post("/guardrail-chat", json={"history": [], "user_input": "a latte", "new_round": True})
    body = r.text
    assert "Anything else?" in body
    assert "[[" not in body                 # tag stripped
    assert '"conclude":false' in body


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

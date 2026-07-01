from app.config import Settings


def test_defaults_when_env_absent(monkeypatch):
    for k in ["FREE_ROUNDS", "MAX_ROUNDS_PER_DAY", "ROUND_COOLDOWN_SECONDS", "TURNS_PER_ROUND"]:
        monkeypatch.delenv(k, raising=False)
    s = Settings()
    assert s.free_rounds == 5
    assert s.max_rounds_per_day == 10
    assert s.round_cooldown_seconds == 30
    assert s.turns_per_round == 5
    assert s.model == "google/gemini-3.1-flash-lite"


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("FREE_ROUNDS", "2")
    monkeypatch.setenv("MAX_ROUNDS_PER_DAY", "4")
    s = Settings()
    assert s.free_rounds == 2
    assert s.max_rounds_per_day == 4

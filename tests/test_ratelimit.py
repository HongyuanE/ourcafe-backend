from app.ratelimit import InMemoryRateLimiter, RoundDecision


def make(now=1000.0):
    clock = {"t": now}
    rl = InMemoryRateLimiter(free_rounds=5, max_rounds_per_day=10, cooldown_seconds=30,
                             now=lambda: clock["t"], today=lambda: "2026-06-26")
    return rl, clock


def test_first_five_rounds_allowed_without_cooldown():
    rl, clock = make()
    for _ in range(5):
        d = rl.start_round("1.2.3.4")
        assert d.allowed and d.retry_after == 0


def test_rounds_six_to_ten_need_cooldown():
    rl, clock = make()
    for _ in range(5):
        rl.start_round("ip")            # burn the 5 free
    d = rl.start_round("ip")            # 6th, immediately after
    assert not d.allowed and 0 < d.retry_after <= 30
    clock["t"] += 30
    d = rl.start_round("ip")            # now cooldown satisfied
    assert d.allowed


def test_eleventh_round_denied_for_the_day():
    rl, clock = make()
    for i in range(10):
        rl.start_round("ip")
        clock["t"] += 30               # satisfy every cooldown
    d = rl.start_round("ip")           # 11th
    assert not d.allowed and d.retry_after < 0   # negative => "come back tomorrow"


def test_separate_ips_independent():
    rl, clock = make()
    for _ in range(5):
        rl.start_round("a")
    d = rl.start_round("b")
    assert d.allowed

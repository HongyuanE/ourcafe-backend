"""Tiered per-IP round limiter.

A "round" is one conversation session. Rounds 1..free_rounds are free; rounds
(free_rounds+1)..max_rounds_per_day require cooldown_seconds since the previous
round start; beyond max_rounds_per_day the IP is done for the day. State resets
per IP per UTC day. In-memory backend for local/tests; DynamoDB for production.
"""
from __future__ import annotations

import hashlib
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class RoundDecision:
    allowed: bool
    retry_after: int  # 0 = go now; >0 = seconds to wait; <0 = done for the day


def _utc_today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def hash_ip(ip: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()[:32]


class RateLimiter(ABC):
    def __init__(self, *, free_rounds: int, max_rounds_per_day: int, cooldown_seconds: int) -> None:
        self.free_rounds = free_rounds
        self.max_rounds_per_day = max_rounds_per_day
        self.cooldown_seconds = cooldown_seconds

    def _decide(self, rounds_started: int, last_start: float, now: float) -> RoundDecision:
        if rounds_started >= self.max_rounds_per_day:
            return RoundDecision(False, -1)
        if rounds_started < self.free_rounds:
            return RoundDecision(True, 0)
        elapsed = now - last_start
        if elapsed >= self.cooldown_seconds:
            return RoundDecision(True, 0)
        return RoundDecision(False, max(1, int(self.cooldown_seconds - elapsed)))

    @abstractmethod
    def start_round(self, ip: str) -> RoundDecision: ...


class InMemoryRateLimiter(RateLimiter):
    def __init__(self, *, free_rounds, max_rounds_per_day, cooldown_seconds,
                 now=time.monotonic, today=_utc_today) -> None:
        super().__init__(free_rounds=free_rounds, max_rounds_per_day=max_rounds_per_day,
                         cooldown_seconds=cooldown_seconds)
        self._now = now
        self._today = today
        self._state: dict[str, tuple[str, int, float]] = {}  # ip -> (day, count, last_start)

    def start_round(self, ip: str) -> RoundDecision:
        now = self._now()
        day = self._today()
        stored_day, count, last = self._state.get(ip, (day, 0, 0.0))
        if stored_day != day:
            count, last = 0, 0.0
        decision = self._decide(count, last, now)
        if decision.allowed:
            self._state[ip] = (day, count + 1, now)
        else:
            self._state[ip] = (day, count, last)
        return decision


class DynamoDBRateLimiter(RateLimiter):
    """One item per IP per day: pk='RL#<hash>', sk=<day>, attrs count/last_start/ttl.

    NOTE: exercised against real DynamoDB on deploy; unit tests use the in-memory
    limiter, so treat first-deploy as the integration test for this class.
    """

    def __init__(self, table_name: str, *, free_rounds, max_rounds_per_day, cooldown_seconds,
                 salt: str) -> None:
        super().__init__(free_rounds=free_rounds, max_rounds_per_day=max_rounds_per_day,
                         cooldown_seconds=cooldown_seconds)
        import boto3
        self._table = boto3.resource("dynamodb").Table(table_name)
        self._salt = salt

    def start_round(self, ip: str) -> RoundDecision:
        # KNOWN CAVEAT: this read-modify-write is NOT atomic — two simultaneous
        # new-round requests from one IP can both read the same count and each be
        # granted a round. Acceptable here because the prepaid OpenRouter balance is
        # the hard cost ceiling; if strict fairness ever matters, switch to
        # update_item with an atomic "ADD count 1" + a ConditionExpression.
        now = time.time()
        day = _utc_today()
        key = {"pk": f"RL#{hash_ip(ip, self._salt)}", "sk": day}
        resp = self._table.get_item(Key=key)
        item = resp.get("Item")
        count = int(item["count"]) if item else 0
        last = float(item["last_start"]) if item else 0.0
        decision = self._decide(count, last, now)
        if decision.allowed:
            # midnight-UTC + 2 days TTL keeps the row well past the day it covers
            ttl = int(now) + 2 * 86400
            self._table.put_item(Item={**key, "count": count + 1, "last_start": int(now), "ttl": ttl})
        return decision


def get_rate_limiter(settings) -> RateLimiter:
    backend = os.getenv("STORAGE_BACKEND", "memory").lower()
    if backend == "dynamodb":
        return DynamoDBRateLimiter(
            os.environ["DYNAMODB_TABLE"],
            free_rounds=settings.free_rounds,
            max_rounds_per_day=settings.max_rounds_per_day,
            cooldown_seconds=settings.round_cooldown_seconds,
            salt=settings.ip_hash_salt,
        )
    return InMemoryRateLimiter(
        free_rounds=settings.free_rounds,
        max_rounds_per_day=settings.max_rounds_per_day,
        cooldown_seconds=settings.round_cooldown_seconds,
    )

# ADR 0002 — Serverless (Lambda + DynamoDB), not an always-on server

- **Status:** Accepted
- **Date:** 2026-06-25

## Context

The leaderboard backend for Ourcafe has a very particular traffic shape: a small,
known audience (friends, fellow developers, people who pick the game up on an
indie platform) who submit a score only when they finish the game's three-day
run. That means **long idle periods punctuated by occasional bursts**, and a tiny
total data volume.

Two ways to host it:

1. **Always-on container** — e.g. ECS Fargate behind an Application Load Balancer.
   Runs (and bills) 24/7 whether or not anyone is playing.
2. **Serverless** — AWS Lambda for compute + DynamoDB for storage. Scales to zero;
   you pay per request and per stored item.

## Decision

Go **serverless: Lambda + DynamoDB**.

- The FastAPI app is wrapped with **Mangum** so the identical code runs locally
  under uvicorn and in Lambda — no rewrite.
- The app is shipped as a **container image** (reusing the ECR repository and the
  secretless OIDC pipeline from ADR 0001); Lambda runs the image directly.
- Storage is a single **DynamoDB** table in on-demand (PAY_PER_REQUEST) mode.

## Consequences

**Positive**

- **~$0 at idle.** No load balancer, no always-running instance. For a hobby game
  leaderboard that sits quiet most of the time, this is the responsible choice —
  and being able to justify it on cost is exactly the operational judgement these
  roles look for.
- **Durable.** DynamoDB persists data across deploys; a container's local disk
  would not.
- **Effectively no scaling work.** Lambda and on-demand DynamoDB absorb bursts
  automatically.
- Reuses the container + ECR + OIDC work already done — nothing wasted.

**Negative / trade-offs**

- **Cold starts** add latency to the first request after idle. For a leaderboard
  this is imperceptible to players; for a latency-critical API it might not be.
- DynamoDB's data model is more constrained than SQL. The leaderboard's
  single-partition "top N by score" query fits it well, but richer queries later
  (e.g. per-player history) will need deliberate key design or a secondary index.
- Local development can't fully mirror DynamoDB without extra tooling, so the
  in-memory backend stands in for tests (see `app/storage.py`).

## Security note (accepted risk)

The submit endpoint is unauthenticated, so scores can be forged. This is a
deliberate, documented trade-off for a low-stakes friends/dev leaderboard with no
login. If integrity ever matters, the cheap next step is a shared submit secret /
HMAC on the request — not full user accounts.

## Alternatives considered

- **ECS Fargate + ALB** — the "classic" container service. Rejected for this
  workload: the ALB alone is ~AU$20/month to keep a near-idle service alive.
- **Relational DB (RDS)** — overkill for one tiny table, and not free at rest
  beyond the 12-month trial. Rejected.

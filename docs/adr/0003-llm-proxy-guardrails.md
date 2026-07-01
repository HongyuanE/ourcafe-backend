# ADR 0003 — LLM proxy with server-side guardrails (not a passthrough)

- **Status:** Accepted
- **Date:** 2026-07-01

## Context

Ourcafe's backend now exposes a `/guardrail-chat` endpoint intended as a
public "try to break it" AI demo. The endpoint is reachable by anyone on the
internet, so several risks need to be addressed up front:

1. **Prompt injection / jailbreaks** — a malicious caller could try to override
   the system prompt or coerce the model into producing harmful output.
2. **Runaway spend** — an automated script could exhaust the OpenRouter balance
   in minutes if there is no rate control.
3. **Cost unpredictability** — per-request spend caps are complex to implement
   correctly; a simpler ceiling was needed.
4. **Model selection** — the demo needs a fast, cheap model; picking the wrong
   one could undermine both cost and latency goals.

## Decision

### Server-side system prompt — never exposed to clients

The system prompt is embedded in `app/guardrail.py` and injected server-side on
every call. The client submits only user-role messages; it never sees or controls
the system turn. This makes guardrail removal structurally impossible from the
client side, regardless of what a caller sends.

### Model locked to `google/gemini-3.1-flash-lite`

The model identifier is hardcoded in the application layer. Clients cannot
select a different model. The choice was made via an internal offline evaluation
(fast, low cost-per-token, adequate quality for a friendly NPC demo); the
evaluation artefact is intentionally not shipped with the code — updating the
model is a one-line code change gated by a code review, not an API parameter.

### Tiered per-IP round rate limiter backed by DynamoDB

Each client IP is hashed (with `IP_HASH_SALT`) before storage so no raw
addresses are persisted. The rate limiter enforces a tiered window strategy:
a tight short-window burst limit and a looser long-window daily cap. DynamoDB
TTL (`ttl` attribute) expires stale window items automatically, keeping the
table small without a maintenance job.

The rate limiter has a known non-atomic race under concurrent requests from the
same IP (read-increment-write is not a transaction). This is intentional: a
compare-and-swap approach would cost more and the brief over-issuance window is
acceptable for a demo.

### Prepaid OpenRouter balance as the hard cost ceiling

Rather than implementing a spend-cap counter (which requires its own atomic
state and can drift), the account is loaded with a fixed prepaid balance.
When the balance is exhausted, OpenRouter returns an error and the endpoint
fails gracefully. This is a simpler, guaranteed hard ceiling that cannot be
bypassed by a counter bug.

### Runtime secrets via AWS SSM SecureString

The `OPENROUTER_API_KEY` is stored as an SSM SecureString, created out-of-band
by the operator. Terraform reads it at apply time via a `data` source; the key
is injected as a Lambda environment variable at deploy, never committed to the
repository. `GUARDRAIL_ALLOWED_ORIGIN` and `IP_HASH_SALT` are non-secret
configuration injected via Terraform variables.

## Consequences

**Positive**

- **Guardrails are unstrippable by clients.** Because the system prompt is
  server-side, no client-side manipulation (custom headers, body overrides) can
  remove it.
- **Bounded abuse cost.** The combination of per-IP rate limiting and a prepaid
  balance cap means worst-case spend is known before deployment and does not
  require runtime monitoring to enforce.
- **Single-model simplicity.** Locking to one model eliminates a class of
  cost/safety surprises; changing it is a deliberate, reviewed action.
- **No standing rate-limit data.** DynamoDB TTL ensures expired windows are
  cleaned up automatically — no cron job or manual purge needed.

**Negative / trade-offs**

- **Non-atomic rate-limit race.** Concurrent bursts from the same IP can
  briefly exceed the limit before the counter catches up. Documented in the
  code; acceptable for a demo with no financial or safety consequence from
  over-issuance by one or two requests.
- **Balance exhaustion fails the endpoint.** There is no graceful degradation
  once the prepaid balance runs out; the endpoint returns an error. This is
  intentional (hard ceiling) but means the demo goes dark rather than
  degrading softly. Acceptable for a personal portfolio demo.
- **OPENROUTER_API_KEY in Lambda environment.** Lambda environment variables
  are visible to anyone with `lambda:GetFunctionConfiguration`. The SSM
  SecureString protects the key at rest, but the resolved value is in Lambda
  config after apply. Mitigated by tight IAM on the Lambda execution role and
  the deploy role; noted as an accepted risk for a demo project.

## Alternatives considered

- **Client-side system prompt** — simplest, but any determined caller can strip
  it. Rejected: guardrails must be server-enforced to be meaningful.
- **Spend-cap counter in DynamoDB** — accurate but adds atomic write complexity
  and can drift if the counter and the OpenRouter call are not in the same
  transaction. Rejected in favour of the prepaid balance ceiling.
- **Model selectable by the caller** — offers flexibility but removes the cost
  and safety guarantee of a known model. Rejected.
- **Redis for rate limiting** — lower latency and native atomic increment, but
  adds a standing cost and operational surface. DynamoDB is already present and
  sufficient at demo scale. Rejected.

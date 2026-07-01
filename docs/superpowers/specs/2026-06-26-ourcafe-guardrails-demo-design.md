# OurCafe Guardrails — public de-hallucination demo (design spec)

**Date:** 2026-06-26
**Repos:** `HongyuanE/ourcafe-backend` (proxy, this repo — branch `feat/guardrail-proxy`) + a new `HongyuanE/ourcafe-guardrails` (frontend, GitHub Pages)
**Source pilot:** `D:\OurCafe\Ourcafe_Unity_Project\Ourcafe_Documents\LLM_Testing\happy_conversation\` — reuse `happy_sim.html` (streaming chat UI) and `system_prompt_FINAL.md` (guardrail prompt to translate).

> **Not part of this project:** the `prompt_pack.md` / `run_eval.py` / 12-scenario kit in that folder was a one-off **internal model-selection bake-off** (already concluded — Gemini 3.1 Flash-Lite won). It is neither ported, published, nor deployed here, and the testing plan does not depend on it.

## Goal

Ship a public, zero-setup, recruiter-facing web demo of the OurCafe NPC chat that
demonstrably resists prompt-injection / gaslighting / role-switching, and that visibly
shows its efficiency (time-to-first-token, tokens, cost). It exists to prove the developer
is an *engineer of reliable AI systems* — not a prompt hobbyist. The proof is the working,
attackable demo itself plus its visible cost/latency indicators; the design rationale lives in
an ADR.

Portfolio framing: "reliability engineering applied to AI." The demo is the third live
flagship (after ourcafe-backend leaderboard and the portfolio site).

## Locked decisions (from brainstorming, 2026-06-26)

1. **Access:** free public demo via a **secure server-side proxy** — visitor just clicks and
   chats; no key entry.
2. **Proxy home:** extend **ourcafe-backend** (new endpoint on the existing FastAPI + Mangum
   Lambda). No new backend service.
3. **Persona/language:** the OurCafe café NPC (celebrating passing an exam), rewritten in
   **English** to welcome any stranger visitor. Bilingual is out of scope for v1.
4. **Demo depth:** full playground — NPC chat + one-click attack buttons + defense log +
   **visual** speed/token/cost indicators.
5. **Model:** **locked** to `google/gemini-3.1-flash-lite`, server-side. **No model switcher.
   No system-prompt reveal.** Visitors cannot see or change the model or the guardrails.
6. **Telemetry is visual:** a live speed gauge (TTFT / tokens-per-sec) and a token+cost
   readout that ticks up as the response streams — not a plain table.
7. **Frontend host:** dedicated **`ourcafe-guardrails`** repo → GitHub Pages, with its own
   README + ADR.
8. **Local-first:** the whole system must run locally (proxy via `uvicorn`, frontend against
   `localhost`) with the key in a `.env`, so the English system prompt can be iterated and
   attacks tested **before any deploy**. Deploy is the final step, only once satisfied.

## The critical correctness rule

**All guardrails and the system prompt live server-side in the proxy — never in the browser.**
The client sends only the visitor's turn + short recent history; the proxy composes the full
guarded prompt and calls the model. If the defense sat in client JS, "leak the system prompt"
would be trivially won by opening devtools. Server-side enforcement is what makes the demo
honest and the "leak the prompt" attack genuinely unwinnable.

## Architecture

```
Browser (ourcafe-guardrails, GitHub Pages)
  │  POST /guardrail-chat  { history[], userInput, attackType?, newRound }   (CORS-locked origin)
  ▼
ourcafe-backend  (FastAPI + Mangum on Lambda; uvicorn locally)
  │  - compose guarded prompt (server-side system prompt + turn state)
  │  - rate-limit check (per-IP daily cap + global monthly spend cap)
  │  - call OpenRouter (google/gemini-3.1-flash-lite, stream=True)
  │  - stream tokens back (SSE); final event carries token usage + server TTFT
  ▼
OpenRouter → Gemini 3.1 Flash-Lite
```

Existing API Gateway already proxies all paths to the single Lambda (Mangum), so no new API
Gateway route resource is required — only the new FastAPI route. Same code path runs under
`uvicorn` locally.

## Backend components (ourcafe-backend)

### New: `app/guardrail.py`
- `POST /guardrail-chat` FastAPI route returning a streaming response (SSE).
- Request model `GuardrailChatRequest`: `history: list[Turn]` (bounded, e.g. last 6 turns),
  `user_input: str`, `attack_type: str | None` (one of the known one-click categories, or
  null for free text), `new_round: bool` (true on the first message of a session → triggers the
  round-limit check). The server tracks the round's `remaining_turns`/`must_conclude_now` from
  the history length and returns `done` when the budget is spent.
- Composes the prompt: server-side English system prompt + a per-turn user message mirroring
  the pilot's structure (scene, NPC, tone, remaining turns, must-conclude flag, the visitor's
  input). History is included to fix the stateless-contradiction gap the pilot README flags.
- Calls OpenRouter via `httpx.AsyncClient` with `stream=True` and
  `stream_options={"include_usage": true}`; measures TTFT server-side; streams text chunks to
  the client as SSE `data:` events, then a final `event: usage` with
  `{prompt_tokens, completion_tokens, ttft_ms}`.
- Model id constant `MODEL = "google/gemini-3.1-flash-lite"`; temperature 0.1 (matches pilot).

### New: `app/prompts/npc_system_prompt_en.md`
- The English system prompt, ported from `system_prompt_FINAL.md`, preserving every defense
  layer: role confinement, identity lockdown (no fabricated memories), scope boundaries (no
  future meetups / contact swaps), no game-state mutation, turn-budget control. Loaded at
  startup. **This is the file the developer iterates on locally.**

### New: rate limiting — tiered, round-based, per IP
- A **round** = one conversation session. It begins when the visitor starts a new chat and ends
  when the model emits `done=true` or the visitor clicks reset. Each round is itself bounded by a
  **turn budget** (server-enforced `remaining_turns` + `must_conclude_now`, ~5 turns / 5–7
  sentences, reusing the pilot's mechanism) so a single round can't be held open to spam tokens.
- Tiered per-IP daily allowance on **starting a round**:
  - Rounds 1–5: start immediately.
  - Rounds 6–10: a 30s cooldown must elapse since the previous round before starting.
  - Round 11+: denied until the next day.
  - Resets daily, per IP.
- Add a small `RateLimiter` abstraction mirroring `Storage`: `InMemoryRateLimiter` (local/tests)
  and `DynamoDBRateLimiter` (deployed), selected by `STORAGE_BACKEND`. It stores, per IP per day,
  `{rounds_started, last_round_start_ts}` in one DynamoDB item keyed by `hash(ip)#date` with a TTL
  that expires at end of day (auto-reset, no PII — IP is salted-hashed, never stored raw). Reuse
  the existing table under a distinct `pk`; no new table.
- The proxy enforces the round check when a request carries `new_round: true`; within-round turns
  are governed by the turn budget, not the round counter.
- **Global cost ceiling = the prepaid OpenRouter balance (<$10).** No separate spend-cap counter.
  If the balance is exhausted (or OpenRouter returns any provider error), the proxy catches it and
  returns a graceful "demo at capacity" payload the frontend renders as a friendly state. Worst-case
  abuse loss is bounded by that balance and is acceptable.

### Config / secrets
- `OPENROUTER_API_KEY` — local: `.env` (git-ignored); Lambda: injected as an env var sourced
  from AWS SSM Parameter Store (SecureString) via Terraform. Never in code or client.
- New env (with defaults): `GUARDRAIL_ALLOWED_ORIGIN` (CORS), `FREE_ROUNDS=5`,
  `MAX_ROUNDS_PER_DAY=10`, `ROUND_COOLDOWN_SECONDS=30`, `TURNS_PER_ROUND=5`, `IP_HASH_SALT`.
- Add `httpx` to `requirements.txt`; `python-dotenv` (dev) for local `.env` loading.

### CORS
- Add FastAPI `CORSMiddleware` limited to the demo origin
  (`https://hongyuane.github.io`) plus `http://localhost:*` for local dev.

### Infra (Terraform)
- `lambda.tf`: add the new env vars; grant the Lambda role `ssm:GetParameter` on the OpenRouter
  key parameter.
- `dynamodb.tf`: enable TTL on the table (attribute `ttl`) for rate-limit items.
- New ADR `docs/adr/0003-llm-proxy-guardrails.md`: why server-side guardrails, the locked model
  (Gemini 3.1 Flash-Lite, chosen via an internal evaluation — kit not shipped), the tiered
  round rate-limit + finite-balance ceiling, cost/latency rationale.

## Frontend components (ourcafe-guardrails repo)

A **tiny Vite app (vanilla TS, no UI framework)** — one small deployable, streaming + gauges in
plain TS, easy GitHub Pages deploy. Port the chat/streaming logic from `happy_sim.html`. Navy/amber
theme matching the portfolio.

- **Chat panel:** NPC bubbles with token streaming; visitor input box.
- **One-click attacks:** buttons for `prompt injection`, `gaslight`, `role-switch`,
  `leak prompt`, `off-topic`, each sending a canned adversarial input with its `attack_type`.
- **Defense log:** when an attack turn completes, append a "held / refused" entry naming the
  attack category. Driven by the known `attack_type` (for one-click) — v1 does not attempt
  server-side classification of free-text attacks (shows a neutral "guardrails active").
- **Visual telemetry:** a speed gauge (fed by `ttft_ms` and tokens/sec derived from the stream)
  and a token + running-cost readout that animates upward during streaming. Cost = tokens ×
  fixed published Gemini-3.1-Flash-Lite rate (constant in the frontend). Static "Gemini 3.1
  Flash-Lite" label — no dropdown.
- **Config:** `API_BASE` switch (`http://localhost:8000` for dev, the prod API Gateway URL for
  deploy).
- **Round status + reset:** a "new chat / reset" control that ends the current round; a small
  rounds-remaining indicator; when in the cooldown tier (rounds 6–10), a 30s countdown before a new
  round can start; a clear "come back tomorrow" state after round 10. The client sends
  `newRound: true` on the first message of each session.
- **Capacity state:** friendly rendering when the proxy returns "demo at capacity" (balance
  exhausted / provider error) or a rate-limit response.
- **"How it works ↗":** link to the repo README/ADR explaining the engineering.

## Local-first workflow (must work before any deploy)

1. `cd ourcafe-backend`, create `.env` with `OPENROUTER_API_KEY=...`, `STORAGE_BACKEND=memory`,
   `GUARDRAIL_ALLOWED_ORIGIN=http://localhost:5173`.
2. `uvicorn app.main:app --reload` (serves `/guardrail-chat` on `localhost:8000`).
3. Run the frontend locally (`API_BASE=http://localhost:8000`); chat, fire every attack button,
   watch the telemetry.
4. Iterate on `app/prompts/npc_system_prompt_en.md`; re-test by firing each attack button and
   free-text probes until the voice and defenses feel right.
5. Only once satisfied: deploy backend (push branch → existing OIDC CI/CD) and frontend
   (GitHub Pages).

## Testing

- **Unit (pytest, in-memory backend, mocked OpenRouter):** prompt assembly includes the system
  prompt + history + turn state; `attack_type` handling; the tiered round limiter (rounds 1–5
  free, 6–10 gated by the 30s cooldown, 11+ denied, daily reset); turn-budget produces `done`;
  graceful capacity/provider-error response. No real network in unit tests.
- **Manual (primary robustness check):** fire every one-click attack live and try free-text
  injection/gaslighting/role-switch/exfiltration probes; confirm the NPC holds, the defense log +
  telemetry update, and the system prompt is not retrievable via any input. Do this locally
  first, then again on the deployed demo.
- **Deploy checks:** backend health after deploy; CORS from the Pages origin; a real end-to-end
  chat on the live demo.

## Portfolio integration (separate small change to old-portfolio, after the demo is live)

- Projects page: a live "OurCafe Guardrails" card linking to the demo (framed as reliability +
  efficiency for AI).
- Home: one teaser line under the hero linking to the demo.

## Out of scope (YAGNI)

Bilingual toggle; visitor-facing model switcher; any system-prompt visibility; accounts/auth;
conversation persistence; server-side free-text attack classification; the in-game Unity wiring
(separate track); the AI-Agile project (its own future flagship).

## Success criteria

- A recruiter with no setup opens the demo, clicks "prompt injection," and watches the NPC stay
  in character while the defense log says "held" and the speed/cost indicators show sub-2s,
  fractions-of-a-cent responses.
- The system prompt and model are not exposed or changeable from the client.
- The public endpoint cannot be abused into meaningful cost (tiered per-IP round limit + the
  finite prepaid OpenRouter balance as the hard ceiling).
- The robustness is self-evident: a visitor can attack it live and watch it hold, with no
  ability to see or alter the model or the guardrails.

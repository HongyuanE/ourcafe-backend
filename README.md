# ourcafe-backend

> Cloud backend for **Ourcafe**, a Unity café game. Starts with the **leaderboard**
> service and is built to grow into the game's online services. Shipped the way real
> software ships: **Infrastructure as Code (Terraform)**, **CI**, a **secretless
> deploy pipeline (GitHub Actions + AWS OIDC)**, and a **serverless, scale-to-zero**
> runtime (AWS Lambda + DynamoDB).

![CI](https://github.com/HongyuanE/ourcafe-backend/actions/workflows/ci.yml/badge.svg)
![Terraform](https://img.shields.io/badge/IaC-Terraform-844FBA?logo=terraform&logoColor=white)
![AWS](https://img.shields.io/badge/Cloud-AWS-232F3E?logo=amazonwebservices&logoColor=FF9900)
![Serverless](https://img.shields.io/badge/Runtime-Lambda%20%2B%20DynamoDB-FF9900?logo=awslambda&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)

## What it does (today)

A small HTTP API that records and ranks leaderboard scores. In Ourcafe a "score"
is the **total cash a player earns across the three-day run**. Players are
identified by a **client-generated PlayerId** (a GUID the game stores locally) —
there is no login.

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/scores` | Submit a finished run: `{ player_id, player_name?, score }` |
| `GET`  | `/leaderboard?limit=N` | Top N scores, highest first |
| `GET`  | `/health` | Liveness probe |

## What it demonstrates

- **Serverless architecture** — Lambda + DynamoDB, **$0 at idle** ([why](docs/adr/0002-serverless-dynamodb.md)).
- **Infrastructure as Code** — every AWS resource defined in Terraform ([`infra/`](infra/)); nothing clicked in the console.
- **Secretless deploys** — GitHub Actions assumes an IAM role via **OIDC**; no AWS keys stored anywhere ([why](docs/adr/0001-secretless-oidc-deploys.md)).
- **Clean architecture** — business logic depends on a `Storage` interface, not on DynamoDB; tests run against an in-memory backend.
- **Least privilege everywhere** — the Lambda's role can touch only the one DynamoDB table; the deploy role can touch only this ECR repo + this function. ECR scans images on push.
- **Tested in CI** — `ruff` + `pytest` on every push and PR.

## Architecture

```
 Unity game ──POST /scores──▶  API Gateway / Function URL
                                      │
                                      ▼
                              AWS Lambda  (FastAPI via Mangum — same code as local)
                                      │
                                      ▼
                              DynamoDB  (on-demand, durable, scale-to-zero)

 Ship pipeline:  push ─▶ GitHub Actions ─(OIDC, no secrets)─▶ ECR ─▶ Lambda
```

## Run it locally

No AWS account needed — local runs use an in-memory store.

```bash
make install
make test                 # ruff + pytest  (in-memory backend)
make run                  # http://localhost:8000/docs  (interactive API)

# try it:
curl -X POST localhost:8000/scores -H 'content-type: application/json' \
     -d '{"player_id":"demo-1","player_name":"Hongyuan","score":4200}'
curl localhost:8000/leaderboard
```

## Game integration (Unity)

On first launch, generate and persist a PlayerId, then POST when a run ends:

```csharp
// once, on first launch
if (!PlayerPrefs.HasKey("player_id"))
    PlayerPrefs.SetString("player_id", System.Guid.NewGuid().ToString());

// when the 3-day run finishes
var payload = JsonUtility.ToJson(new {
    player_id   = PlayerPrefs.GetString("player_id"),
    player_name = displayName,
    score       = totalCash
});
// POST payload to {API_URL}/scores
```

## Deploy

All infrastructure is Terraform. Because a container-image Lambda needs its image
to exist first, deploy is two applies (base infra → CI pushes image → serving
layer). Full walkthrough in [`infra/README.md`](infra/README.md).

## Cost

Built to stay at **~$0 when idle**: on-demand DynamoDB (pay per request), Lambda
(pay per invocation), and ECR storage bounded to the 10 most recent images. A
quiet week costs essentially nothing.

## Roadmap

- [x] Leaderboard API with a storage abstraction (in-memory + DynamoDB)
- [x] Tests, CI (lint/test/build), secretless OIDC pipeline to ECR
- [x] DynamoDB table (Terraform)
- [x] Lambda + Function URL serving layer (live HTTPS endpoint)
- [ ] Per-player history (`GET /scores/{player_id}`)
- [ ] **Phase 1+:** AI NPC companion service — NPCs chat with players via a dedicated app

## Project layout

```
app/          FastAPI service: models · storage (in-memory + DynamoDB) · API
tests/        pytest suite (in-memory backend)
infra/        Terraform: DynamoDB · ECR · GitHub OIDC role
docs/adr/     architecture decision records (the "why")
Dockerfile    multi-stage, non-root  (also the Lambda image)
```

# ADR 0001 — Secretless deploys via GitHub OIDC (not stored AWS keys)

- **Status:** Accepted
- **Date:** 2026-06-25

## Context

The CI/CD pipeline needs to authenticate to AWS to push container images to ECR
(and later, to update an ECS service). There are two common ways to give GitHub
Actions AWS permissions:

1. **Long-lived IAM access keys** stored as GitHub repository secrets.
2. **OIDC federation** — GitHub issues a short-lived, signed identity token for
   each workflow run, which AWS exchanges for temporary credentials.

## Decision

Use **OIDC federation**. Terraform provisions a GitHub OIDC identity provider and
an IAM role whose trust policy only accepts tokens from this specific repository
(`repo:HongyuanE/iac-cicd-pipeline:*`). The workflow requests `id-token: write`
and assumes that role at runtime.

## Consequences

**Positive**

- **No secrets to leak.** There are no static AWS keys in GitHub to be exfiltrated,
  committed by accident, or rotated manually.
- Credentials are **short-lived** (minutes) and **scoped** to one repo and one
  ECR repository (least privilege).
- This is the pattern AWS and GitHub both recommend, and what a mature team expects
  to see — it signals operational maturity, not just "it works".

**Negative / trade-offs**

- More moving parts than pasting an access key: an OIDC provider, a trust policy,
  and a role must be set up correctly first.
- The OIDC provider is **account-wide** (one per account for GitHub), which needs
  handling if multiple repos use it (documented in `infra/README.md`).

## Alternatives considered

- **Stored access keys** — simplest to set up, but a standing liability and widely
  considered an anti-pattern for CI. Rejected.
- **A self-hosted runner with an instance role** — avoids keys too, but adds runner
  maintenance and cost that isn't justified for a portfolio-scale project. Rejected.

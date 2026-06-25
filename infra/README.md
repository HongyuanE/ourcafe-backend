# Infrastructure (Terraform)

Provisions the AWS resources for the Ourcafe backend:

- **DynamoDB table** — durable leaderboard storage (on-demand, scale-to-zero).
- **ECR repository** — stores the Lambda container image (scan-on-push, keep last 10).
- **GitHub OIDC provider + IAM role** — lets GitHub Actions push images and update the Lambda using short-lived tokens, with **no stored AWS keys**.
- **Lambda function + Function URL** — the public HTTPS API (created in phase 2).

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/downloads) ≥ 1.6
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) configured (`aws configure`) with rights to create the above
- An AWS account (Free Tier is fine)

## Why two applies?

A container-image Lambda needs its image to **already exist in ECR** when it's
created — but the image is built and pushed by CI, which needs the ECR repo and
the OIDC role to exist first. So:

```
Phase 1: terraform apply                      # ECR, DynamoDB, OIDC role, exec role
   ↓     (set GitHub variables, trigger CI → image lands in ECR)
Phase 2: terraform apply -var=deploy_lambda=true   # Lambda + Function URL
```

## Phase 1 — base infrastructure

```bash
terraform init
terraform validate
terraform plan
terraform apply           # creates everything EXCEPT the Lambda
```

Then wire the outputs into GitHub Actions **variables**
(repo → Settings → Secrets and variables → Actions → **Variables**):

```bash
terraform output github_actions_role_arn   # → GitHub variable AWS_ROLE_ARN
terraform output aws_region                # → GitHub variable AWS_REGION
```

Now run the **Build and Push to ECR** workflow (push to `main`, or use
"Run workflow"). With `AWS_ROLE_ARN` set, it authenticates via OIDC, builds the
image, and pushes it to ECR.

## Phase 2 — serving layer

Once an image is in ECR:

```bash
terraform apply -var="deploy_lambda=true"
terraform output api_endpoint       # your live HTTPS endpoint
```

Test it:

```bash
URL=$(terraform output -raw api_endpoint)
curl -X POST "$URL/scores" -H 'content-type: application/json' \
     -d '{"player_id":"demo-1","player_name":"Hongyuan","score":4200}'
curl "$URL/leaderboard"
```

From now on, every push to `main` rebuilds the image and updates the Lambda
automatically — no further Terraform needed for code changes.

## Notes

- **Region/repo defaults:** ap-southeast-2 (Sydney), `HongyuanE/ourcafe-backend`.
- **OIDC provider is account-wide:** only one per account for GitHub. If you ever
  create another repo that needs it, reference the existing provider via a data
  source instead of recreating it.

## Teardown

```bash
terraform destroy
```

On-demand DynamoDB + Lambda cost ~nothing at rest, but `destroy` keeps the
account clean.

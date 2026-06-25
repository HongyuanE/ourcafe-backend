# Infrastructure (Terraform)

Provisions the AWS resources for the CI/CD pipeline:

- **ECR repository** — stores the container image (scan-on-push, keep last 10 images).
- **GitHub OIDC provider + IAM role** — lets GitHub Actions push to ECR using short-lived tokens, with **no stored AWS keys**.

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/downloads) ≥ 1.6
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) configured with credentials that can create ECR + IAM resources (`aws configure`)
- An AWS account (Free Tier is fine)

## Usage

```bash
terraform init      # download the AWS provider
terraform fmt       # format check
terraform validate  # syntax / type check  (run this before plan)
terraform plan      # preview — nothing is created yet
terraform apply     # create the resources
```

Defaults target **ap-southeast-2 (Sydney)** and the repo **HongyuanE/iac-cicd-pipeline**. Override per-run if needed:

```bash
terraform apply -var="aws_region=ap-southeast-2" -var="github_repo=iac-cicd-pipeline"
```

## After apply

Read the outputs and wire them into GitHub Actions **variables**:

```bash
terraform output github_actions_role_arn   # → GitHub variable AWS_ROLE_ARN
terraform output aws_region                # → GitHub variable AWS_REGION
terraform output ecr_repository_url        # (informational)
```

## Heads-up: the OIDC provider is account-wide

An AWS account can have only **one** OIDC provider for `token.actions.githubusercontent.com`. If you've already created it (for another repo/project), delete the `aws_iam_openid_connect_provider.github` resource in [`github-oidc.tf`](github-oidc.tf) and reference the existing one with a data source instead — otherwise `apply` will fail with "provider already exists".

## Teardown

```bash
terraform destroy
```

Nothing here incurs ongoing cost at rest, but `destroy` keeps the account clean.

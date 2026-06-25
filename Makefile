.PHONY: install test lint fmt run image tf-init tf-plan tf-apply tf-apply-lambda

install:        ## Install dev dependencies
	pip install -r requirements-dev.txt

test:           ## Run the test suite
	pytest

lint:           ## Static checks
	ruff check .

fmt:            ## Auto-format / fix
	ruff check --fix .

run:            ## Run the app locally with hot reload (no container, no AWS)
	uvicorn app.main:app --reload

image:          ## Build the Lambda container image (CI does this for real)
	docker build -t ourcafe-backend:local .

tf-init:        ## Initialise Terraform
	cd infra && terraform init

tf-plan:        ## Preview infrastructure changes
	cd infra && terraform plan

tf-apply:       ## Apply base infra (ECR, DynamoDB, IAM/OIDC) — run this first
	cd infra && terraform apply

tf-apply-lambda: ## Apply with the serving layer (run after CI has pushed an image)
	cd infra && terraform apply -var="deploy_lambda=true"

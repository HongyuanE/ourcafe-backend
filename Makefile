.PHONY: install test lint fmt run docker-build docker-run compose-up tf-init tf-plan

install:        ## Install dev dependencies
	pip install -r requirements-dev.txt

test:           ## Run the test suite
	pytest

lint:           ## Static checks
	ruff check .

fmt:            ## Auto-format / fix
	ruff check --fix .

run:            ## Run the app locally (no container)
	uvicorn app.main:app --reload

docker-build:   ## Build the container image
	docker build -t iac-cicd-pipeline:local .

docker-run:     ## Run the container locally on :8000
	docker run --rm -p 8000:8000 iac-cicd-pipeline:local

compose-up:     ## Build + run via docker compose
	docker compose up --build

tf-init:        ## Initialise Terraform
	cd infra && terraform init

tf-plan:        ## Preview infrastructure changes
	cd infra && terraform plan

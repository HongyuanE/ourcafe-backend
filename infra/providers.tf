provider "aws" {
  region = var.aws_region

  # Every resource is tagged automatically — makes cost attribution and cleanup trivial.
  default_tags {
    tags = {
      Project   = "iac-cicd-pipeline"
      ManagedBy = "Terraform"
      Owner     = var.github_owner
    }
  }
}

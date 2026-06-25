terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Remote state backend — uncomment and configure once you've created an S3 bucket.
  # Keeping state local is fine for a solo portfolio project; remote state is the
  # team-grade choice and worth showing you know it exists.
  #
  # backend "s3" {
  #   bucket = "your-tf-state-bucket"
  #   key    = "iac-cicd-pipeline/terraform.tfstate"
  #   region = "ap-southeast-2"
  # }
}

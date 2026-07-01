variable "aws_region" {
  description = "AWS region to deploy into. Sydney is the closest region to Melbourne."
  type        = string
  default     = "ap-southeast-2"
}

variable "github_owner" {
  description = "GitHub username/org that owns the repository."
  type        = string
  default     = "HongyuanE"
}

variable "github_repo" {
  description = "Repository name. Used to scope which repo may assume the deploy role."
  type        = string
  default     = "ourcafe-backend"
}

variable "deploy_lambda" {
  description = <<-EOT
    Whether to create the Lambda function + Function URL. Keep false for the first
    apply (the container image must exist in ECR first); flip to true for the
    second apply once CI has pushed an image.
  EOT
  type        = bool
  default     = false
}

variable "image_tag" {
  description = "ECR image tag the Lambda is first created from. CI updates it thereafter."
  type        = string
  default     = "latest"
}

variable "ip_hash_salt" {
  description = "Salt used when hashing client IPs for the per-IP rate limiter. Override in production; the default is safe for a public demo."
  type        = string
  default     = "ourcafe-demo-salt"
}

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

output "ecr_repository_url" {
  description = "Container image destination — `docker push` here."
  value       = aws_ecr_repository.app.repository_url
}

output "github_actions_role_arn" {
  description = "Set this as the GitHub Actions variable AWS_ROLE_ARN."
  value       = aws_iam_role.github_actions.arn
}

output "aws_region" {
  description = "Set this as the GitHub Actions variable AWS_REGION."
  value       = var.aws_region
}

output "dynamodb_table_name" {
  description = "Set as the app's DYNAMODB_TABLE env var (with STORAGE_BACKEND=dynamodb)."
  value       = aws_dynamodb_table.leaderboard.name
}

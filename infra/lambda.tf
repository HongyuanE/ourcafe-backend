# The serving layer: the API runs as a container-image Lambda, exposed over a
# public Function URL (no API Gateway needed). Created only when var.deploy_lambda
# is true — the image must exist in ECR first (pushed by CI), so the first apply
# provisions everything else, then a second apply (deploy_lambda=true) adds this.

# ---- Execution role ----
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_exec" {
  name               = "${var.github_repo}-lambda-exec"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

# Write logs to CloudWatch.
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Least privilege: the function may only PutItem/Query the leaderboard table.
resource "aws_iam_role_policy" "lambda_dynamodb" {
  name = "dynamodb-access"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem", "dynamodb:Query"]
        Resource = aws_dynamodb_table.leaderboard.arn
      }
    ]
  })
}

# Bounded log retention — keeps CloudWatch costs from creeping.
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.github_repo}"
  retention_in_days = 14
}

# ---- The function ----
resource "aws_lambda_function" "api" {
  count         = var.deploy_lambda ? 1 : 0
  function_name = var.github_repo
  role          = aws_iam_role.lambda_exec.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.app.repository_url}:${var.image_tag}"
  timeout       = 15
  memory_size   = 256

  environment {
    variables = {
      STORAGE_BACKEND = "dynamodb"
      DYNAMODB_TABLE  = aws_dynamodb_table.leaderboard.name
    }
  }

  # CI updates the image on each deploy via `update-function-code`; don't let
  # Terraform revert it on the next apply.
  lifecycle {
    ignore_changes = [image_uri]
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
}

# The public HTTPS front door is an API Gateway HTTP API — see apigateway.tf.

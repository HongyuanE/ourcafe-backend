# The serving layer: the API runs as a container-image Lambda, exposed over a
# public Function URL (no API Gateway needed). Created only when var.deploy_lambda
# is true — the image must exist in ECR first (pushed by CI), so the first apply
# provisions everything else, then a second apply (deploy_lambda=true) adds this.

# ---- SSM parameters ----
# The OpenRouter API key is stored as an SSM SecureString by the operator out-of-band;
# Terraform only reads it here — the secret value never appears in state as plaintext.
data "aws_ssm_parameter" "openrouter_key" {
  name            = "/ourcafe/openrouter_api_key"
  with_decryption = true
}

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

# Least privilege: leaderboard uses PutItem/Query; the guardrail rate limiter also
# reads its per-IP counter with GetItem.
resource "aws_iam_role_policy" "lambda_dynamodb" {
  name = "dynamodb-access"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query"]
        Resource = aws_dynamodb_table.leaderboard.arn
      }
    ]
  })
}

# Least privilege: the function may only read the single OpenRouter key parameter.
resource "aws_iam_role_policy" "lambda_ssm" {
  name = "ssm-openrouter-key"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter"]
        Resource = "arn:aws:ssm:*:*:parameter/ourcafe/openrouter_api_key"
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
      STORAGE_BACKEND          = "dynamodb"
      DYNAMODB_TABLE           = aws_dynamodb_table.leaderboard.name
      OPENROUTER_API_KEY       = data.aws_ssm_parameter.openrouter_key.value
      GUARDRAIL_ALLOWED_ORIGIN = "https://hongyuane.github.io"
      IP_HASH_SALT             = var.ip_hash_salt
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

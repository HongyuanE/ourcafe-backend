# Public HTTP API in front of the Lambda — the API's front door.
#
# Chosen over a Lambda Function URL: this account refused public (NONE-auth)
# Function-URL invokes despite a canonical resource policy. An API Gateway HTTP
# API is public by default, serves from the standard execute-api endpoint, and is
# the canonical serverless API pattern. The Lambda underneath is unchanged.

resource "aws_apigatewayv2_api" "http" {
  count         = var.deploy_lambda ? 1 : 0
  name          = "${var.github_repo}-http"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST"]
    allow_headers = ["content-type"]
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  count                  = var.deploy_lambda ? 1 : 0
  api_id                 = aws_apigatewayv2_api.http[0].id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api[0].invoke_arn
  payload_format_version = "2.0" # same event shape Mangum already handles
}

resource "aws_apigatewayv2_route" "default" {
  count     = var.deploy_lambda ? 1 : 0
  api_id    = aws_apigatewayv2_api.http[0].id
  route_key = "$default" # send every path/method to the FastAPI app
  target    = "integrations/${aws_apigatewayv2_integration.lambda[0].id}"
}

resource "aws_apigatewayv2_stage" "default" {
  count       = var.deploy_lambda ? 1 : 0
  api_id      = aws_apigatewayv2_api.http[0].id
  name        = "$default"
  auto_deploy = true
}

# Allow API Gateway to invoke the function.
resource "aws_lambda_permission" "apigw" {
  count         = var.deploy_lambda ? 1 : 0
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api[0].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http[0].execution_arn}/*/*"
}

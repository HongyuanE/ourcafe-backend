# Durable storage for leaderboard entries.
#
# PAY_PER_REQUEST (on-demand) billing means there is NO idle cost — you pay only
# per read/write, which at "a few friends finishing a run" volume is effectively
# free. No capacity to provision, no servers to manage.

resource "aws_dynamodb_table" "leaderboard" {
  name         = "ourcafe-leaderboard"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  # TTL: the guardrail rate-limiter writes items with a `ttl` Unix epoch attribute.
  # DynamoDB deletes them automatically once that timestamp passes, so the table
  # never accumulates stale rate-limit windows.
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }
}

# Migrated from ai.yml. Existing physical names are preserved.

resource "aws_cloudwatch_log_group" "parser_log_group" {
  provider          = aws.ai
  count             = var.enable_ai ? 1 : 0
  tags              = { "PROJECT_NAME" = var.project_name }
  name              = "/aws/lambda/${var.project_name}-agenda-parser"
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role_policy" "parser_role" {
  provider = aws.ai
  count    = var.enable_ai ? 1 : 0
  name     = "AgendaParserRuntime"
  role     = aws_iam_role.parser_role[0].id
  policy = jsonencode({
    "Version" = "2012-10-17",
    "Statement" = [{
      "Sid"    = "OwnLogs",
      "Effect" = "Allow",
      "Action" = ["logs:CreateLogStream",
      "logs:PutLogEvents"],
      "Resource" = "arn:${data.aws_partition.current.partition}:logs:${var.ai_region}:${var.ai_account_id}:log-group:/aws/lambda/${var.project_name}-agenda-parser:*"
      },
      {
        "Sid"    = "BedrockInference",
        "Effect" = "Allow",
        "Action" = ["bedrock-mantle:CreateInference",
        "bedrock:InvokeModel"],
        "Resource" = "*"
    }]
  })
}

resource "aws_iam_role" "parser_role" {
  provider = aws.ai
  count    = var.enable_ai ? 1 : 0
  tags     = { "PROJECT_NAME" = var.project_name }
  name     = "peach-ai-sonnet-ParserRole-bKIYeXFKNxBU"
  assume_role_policy = jsonencode({
    "Version" = "2012-10-17",
    "Statement" = [{
      "Effect" = "Allow",
      "Principal" = {
        "Service" = "lambda.amazonaws.com"
      },
      "Action" = "sts:AssumeRole"
    }]
  })
}

resource "aws_lambda_function" "parser_function" {
  provider                       = aws.ai
  count                          = var.enable_ai ? 1 : 0
  tags                           = { "PROJECT_NAME" = var.project_name }
  function_name                  = "${var.project_name}-agenda-parser"
  package_type                   = "Image"
  architectures                  = [var.architecture]
  memory_size                    = 512
  timeout                        = 30
  role                           = aws_iam_role.parser_role[0].arn
  image_uri                      = var.parser_image_uri
  reserved_concurrent_executions = var.reserved_concurrency > 0 ? var.reserved_concurrency : -1
  image_config {
    command = ["app.ai.agenda_lambda.handler"]
  }
  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.parser_log_group[0].name
  }
  environment {
    variables = {
      "APP_ENV"              = "production",
      "PARSER_MODEL"         = var.parser_model,
      "PARSER_REGION"        = var.bedrock_region,
      "PARSER_API"           = var.parser_api,
      "COGNITO_REGION"       = var.auth_region,
      "COGNITO_USER_POOL_ID" = aws_cognito_user_pool.user_pool.id,
      "COGNITO_CLIENT_ID"    = aws_cognito_user_pool_client.user_pool_client.id
    }
  }
  depends_on = [aws_iam_role_policy.parser_role]
}

resource "aws_lambda_function_url" "parser_url" {
  provider           = aws.ai
  count              = var.enable_ai ? 1 : 0
  function_name      = aws_lambda_function.parser_function[0].function_name
  authorization_type = "NONE"
  cors {
    allow_origins = [var.site_origin]
    allow_methods = ["POST"]
    allow_headers = ["authorization", "content-type"]
    max_age       = 300
  }
}

resource "aws_lambda_permission" "parser_url_permission" {
  provider               = aws.ai
  count                  = var.enable_ai ? 1 : 0
  function_name          = aws_lambda_function.parser_function[0].function_name
  action                 = "lambda:InvokeFunctionUrl"
  principal              = "*"
  function_url_auth_type = "NONE"
  statement_id           = "peach-ai-sonnet-ParserUrlPermission-bFFWkCUOiXm4"
}

resource "aws_lambda_permission" "parser_invoke_permission" {
  provider                 = aws.ai
  count                    = var.enable_ai ? 1 : 0
  function_name            = aws_lambda_function.parser_function[0].function_name
  action                   = "lambda:InvokeFunction"
  principal                = "*"
  invoked_via_function_url = true
  statement_id             = "peach-ai-sonnet-ParserInvokePermission-dplwUS0Qp72x"
}

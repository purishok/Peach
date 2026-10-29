# Migrated from reports.yml. Existing physical names are preserved.

resource "aws_s3_bucket" "reports_bucket" {
  tags          = { PROJECT_NAME = var.project_name }
  bucket        = "${var.project_name}-reports-${data.aws_caller_identity.current.account_id}"
  force_destroy = false
  lifecycle { prevent_destroy = true }
}

resource "aws_s3_bucket_policy" "reports_bucket_policy" {
  bucket = aws_s3_bucket.reports_bucket.bucket
  policy = jsonencode({
    "Version" = "2012-10-17",
    "Statement" = [{
      "Sid"       = "DenyInsecureTransport",
      "Effect"    = "Deny",
      "Principal" = "*",
      "Action"    = "s3:*",
      "Resource" = [aws_s3_bucket.reports_bucket.arn,
      "${aws_s3_bucket.reports_bucket.arn}/*"],
      "Condition" = {
        "Bool" = {
          "aws:SecureTransport" = "false"
        }
      }
    }]
  })
}

resource "aws_vpc_endpoint" "s3_gateway_endpoint" {
  tags              = { PROJECT_NAME = var.project_name }
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = var.route_table_ids
}

resource "aws_sqs_queue" "report_requests_dlq" {
  max_message_size          = 1048576
  tags                      = { PROJECT_NAME = var.project_name }
  name                      = "${var.project_name}-report-requests-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "report_requests_queue" {
  max_message_size           = 1048576
  tags                       = { PROJECT_NAME = var.project_name }
  name                       = "${var.project_name}-report-requests"
  message_retention_seconds  = 345600
  receive_wait_time_seconds  = 20
  visibility_timeout_seconds = 360
  sqs_managed_sse_enabled    = true
  redrive_policy             = jsonencode({ "deadLetterTargetArn" = aws_sqs_queue.report_requests_dlq.arn, "maxReceiveCount" = 3 })
}

resource "aws_sqs_queue_policy" "requests" {
  queue_url = aws_sqs_queue.report_requests_queue.url
  policy = jsonencode({
    "Version" = "2012-10-17",
    "Statement" = [{
      "Sid"       = "DenyInsecureTransportRequests",
      "Effect"    = "Deny",
      "Principal" = "*",
      "Action"    = "sqs:*",
      "Resource"  = aws_sqs_queue.report_requests_queue.arn,
      "Condition" = {
        "Bool" = {
          "aws:SecureTransport" = "false"
        }
      }
      },
      {
        "Sid"       = "DenyInsecureTransportDlq",
        "Effect"    = "Deny",
        "Principal" = "*",
        "Action"    = "sqs:*",
        "Resource"  = aws_sqs_queue.report_requests_dlq.arn,
        "Condition" = {
          "Bool" = {
            "aws:SecureTransport" = "false"
          }
        }
    }]
  })
}

resource "aws_sqs_queue_policy" "dlq" {
  queue_url = aws_sqs_queue.report_requests_dlq.url
  policy = jsonencode({
    "Version" = "2012-10-17",
    "Statement" = [{
      "Sid"       = "DenyInsecureTransportRequests",
      "Effect"    = "Deny",
      "Principal" = "*",
      "Action"    = "sqs:*",
      "Resource"  = aws_sqs_queue.report_requests_queue.arn,
      "Condition" = {
        "Bool" = {
          "aws:SecureTransport" = "false"
        }
      }
      },
      {
        "Sid"       = "DenyInsecureTransportDlq",
        "Effect"    = "Deny",
        "Principal" = "*",
        "Action"    = "sqs:*",
        "Resource"  = aws_sqs_queue.report_requests_dlq.arn,
        "Condition" = {
          "Bool" = {
            "aws:SecureTransport" = "false"
          }
        }
    }]
  })
}

resource "aws_security_group" "report_builder_security_group" {
  tags        = { PROJECT_NAME = var.project_name, Name = "${var.project_name}-report-builder" }
  vpc_id      = var.vpc_id
  description = "${var.project_name} weekly report builder"
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_vpc_security_group_ingress_rule" "database_ingress_from_report_builder" {
  security_group_id            = var.database_security_group_id
  referenced_security_group_id = aws_security_group.report_builder_security_group.id
  description                  = "Peach weekly report builder"
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

resource "aws_cloudwatch_log_group" "report_builder_log_group" {
  tags              = { PROJECT_NAME = var.project_name }
  name              = "/aws/lambda/${var.project_name}-report-builder"
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role_policy" "report_builder_role" {
  name = "ReportBuilderRuntime"
  role = aws_iam_role.report_builder_role.id
  policy = jsonencode({
    "Version" = "2012-10-17",
    "Statement" = [{
      "Sid"    = "Logs",
      "Effect" = "Allow",
      "Action" = ["logs:CreateLogStream",
      "logs:PutLogEvents"],
      "Resource" = "${aws_cloudwatch_log_group.report_builder_log_group.arn}:*:*"
      },
      {
        "Sid"    = "VpcNetworking",
        "Effect" = "Allow",
        "Action" = ["ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface",
          "ec2:AssignPrivateIpAddresses",
        "ec2:UnassignPrivateIpAddresses"],
        "Resource" = "*"
      },
      {
        "Sid"    = "ConsumeQueue",
        "Effect" = "Allow",
        "Action" = ["sqs:ReceiveMessage",
          "sqs:DeleteMessage",
        "sqs:GetQueueAttributes"],
        "Resource" = aws_sqs_queue.report_requests_queue.arn
      },
      {
        "Sid"      = "WriteReports",
        "Effect"   = "Allow",
        "Action"   = "s3:PutObject",
        "Resource" = "${aws_s3_bucket.reports_bucket.arn}/reports/*"
    }]
  })
}

resource "aws_iam_role" "report_builder_role" {
  tags = { PROJECT_NAME = var.project_name }
  name = "peach-reports-ReportBuilderRole-fgH98bfpuOcI"
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

resource "aws_lambda_function" "report_builder_function" {
  tags          = { PROJECT_NAME = var.project_name }
  function_name = "${var.project_name}-report-builder"
  description   = "Build Peach weekly meeting CSV reports"
  package_type  = "Image"
  architectures = [var.architecture]
  memory_size   = var.builder_memory_size
  timeout       = 60
  role          = aws_iam_role.report_builder_role.arn
  image_uri     = var.reports_image_uri
  image_config {
    command = ["app.reports.lambda_handler.handler"]
  }
  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.report_builder_log_group.name
  }
  environment {
    variables = {
      "APP_ENV"                  = "production",
      "DB_POOLING"               = "false",
      "DATABASE_URL"             = jsondecode(data.aws_secretsmanager_secret_version.database.secret_string)["database_url"],
      "REPORTS_BUCKET"           = aws_s3_bucket.reports_bucket.bucket,
      "REPORT_FAILURE_TEST_WEEK" = var.failure_test_week,
      "LOG_LEVEL"                = "INFO"
    }
  }
  vpc_config {
    subnet_ids         = var.subnet_ids
    security_group_ids = [aws_security_group.report_builder_security_group.id]
  }
  depends_on = [aws_vpc_security_group_ingress_rule.database_ingress_from_report_builder, aws_iam_role_policy.report_builder_role]
}

resource "aws_lambda_event_source_mapping" "report_queue_event_source" {
  tags             = { PROJECT_NAME = var.project_name }
  batch_size       = 1
  enabled          = true
  event_source_arn = aws_sqs_queue.report_requests_queue.arn
  function_name    = aws_lambda_function.report_builder_function.function_name
}

resource "aws_iam_role_policy" "scheduler_role" {
  name = "SendWeeklyReportCommand"
  role = aws_iam_role.scheduler_role.id
  policy = jsonencode({
    "Version" = "2012-10-17",
    "Statement" = [{
      "Effect"   = "Allow",
      "Action"   = "sqs:SendMessage",
      "Resource" = aws_sqs_queue.report_requests_queue.arn
    }]
  })
}

resource "aws_iam_role" "scheduler_role" {
  tags = { PROJECT_NAME = var.project_name }
  name = "peach-reports-SchedulerRole-BSH6JWvXp1h3"
  assume_role_policy = jsonencode({
    "Version" = "2012-10-17",
    "Statement" = [{
      "Effect" = "Allow",
      "Principal" = {
        "Service" = "scheduler.amazonaws.com"
      },
      "Action" = "sts:AssumeRole",
      "Condition" = {
        "StringEquals" = {
          "aws:SourceAccount" = data.aws_caller_identity.current.account_id,
          "aws:SourceArn"     = "arn:${data.aws_partition.current.partition}:scheduler:${var.region}:${data.aws_caller_identity.current.account_id}:schedule-group/default"
        }
      }
    }]
  })
}

resource "aws_scheduler_schedule" "weekly_report_schedule" {
  name                         = "${var.project_name}-weekly-reports"
  description                  = "Every Monday at 07:00 Europe/Kyiv"
  state                        = "ENABLED"
  schedule_expression          = "cron(0 7 ? * MON *)"
  schedule_expression_timezone = "Europe/Kyiv"
  flexible_time_window { mode = "OFF" }
  target {
    arn      = aws_sqs_queue.report_requests_queue.arn
    role_arn = aws_iam_role.scheduler_role.arn
    input    = "{\"source\":\"schedule\",\"week\":null}"
    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 3
    }
  }
  depends_on = [aws_iam_role_policy.scheduler_role]
}

resource "aws_sesv2_email_identity" "ses_email_identity" {
  count          = var.create_ses_email_identity ? 1 : 0
  email_identity = var.ses_identity_name
}

resource "aws_cloudwatch_log_group" "report_mailer_log_group" {
  tags              = { PROJECT_NAME = var.project_name }
  name              = "/aws/lambda/${var.project_name}-report-mailer"
  retention_in_days = var.log_retention_days
}

resource "aws_iam_role_policy" "report_mailer_role" {
  name = "ReportMailerRuntime"
  role = aws_iam_role.report_mailer_role.id
  policy = jsonencode({
    "Version" = "2012-10-17",
    "Statement" = [{
      "Sid"    = "Logs",
      "Effect" = "Allow",
      "Action" = ["logs:CreateLogStream",
      "logs:PutLogEvents"],
      "Resource" = "${aws_cloudwatch_log_group.report_mailer_log_group.arn}:*:*"
      },
      {
        "Sid"      = "ReadReports",
        "Effect"   = "Allow",
        "Action"   = "s3:GetObject",
        "Resource" = "arn:${data.aws_partition.current.partition}:s3:::${var.project_name}-reports-${data.aws_caller_identity.current.account_id}/reports/*"
      },
      {
        "Sid"    = "SendReportEmail",
        "Effect" = "Allow",
        "Action" = ["ses:SendEmail",
        "ses:SendRawEmail"],
        "Resource" = "arn:${data.aws_partition.current.partition}:ses:${var.region}:${data.aws_caller_identity.current.account_id}:identity/${var.ses_identity_name}"
    }]
  })
}

resource "aws_iam_role" "report_mailer_role" {
  tags = { PROJECT_NAME = var.project_name }
  name = "peach-reports-ReportMailerRole-mio3Ev1tiq9c"
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

resource "aws_lambda_function" "report_mailer_function" {
  tags          = { PROJECT_NAME = var.project_name }
  function_name = "${var.project_name}-report-mailer"
  description   = "Email Peach weekly meeting CSV reports"
  package_type  = "Image"
  architectures = [var.architecture]
  memory_size   = 256
  timeout       = 30
  role          = aws_iam_role.report_mailer_role.arn
  image_uri     = var.reports_image_uri
  image_config {
    command = ["app.reports.mailer.handler"]
  }
  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.report_mailer_log_group.name
  }
  environment {
    variables = { "REPORT_SENDER" = var.report_sender_email, "REPORT_RECIPIENTS" = var.report_recipient_emails, "LOG_LEVEL" = "INFO" }
  }
  depends_on = [aws_iam_role_policy.report_mailer_role]
}

resource "aws_lambda_permission" "mailer_invoke_permission" {
  function_name  = aws_lambda_function.report_mailer_function.function_name
  action         = "lambda:InvokeFunction"
  principal      = "s3.amazonaws.com"
  source_account = data.aws_caller_identity.current.account_id
  source_arn     = "arn:${data.aws_partition.current.partition}:s3:::${var.project_name}-reports-${data.aws_caller_identity.current.account_id}"
  statement_id   = "peach-reports-MailerInvokePermission-p5TSfT9KnVDF"
}

resource "aws_s3_bucket_versioning" "reports" {
  bucket = aws_s3_bucket.reports_bucket.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  bucket = aws_s3_bucket.reports_bucket.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_ownership_controls" "reports" {
  bucket = aws_s3_bucket.reports_bucket.id
  rule { object_ownership = "BucketOwnerEnforced" }
}

resource "aws_s3_bucket_public_access_block" "reports" {
  bucket                  = aws_s3_bucket.reports_bucket.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "reports" {
  bucket = aws_s3_bucket.reports_bucket.id
  rule {
    id     = "DeleteReportsAfter90Days"
    status = "Enabled"
    filter { prefix = "reports/" }
    expiration { days = 90 }
    noncurrent_version_expiration { noncurrent_days = 90 }
  }
  depends_on = [aws_s3_bucket_versioning.reports]
}

resource "aws_s3_bucket_notification" "reports" {
  bucket = aws_s3_bucket.reports_bucket.id
  lambda_function {
    lambda_function_arn = aws_lambda_function.report_mailer_function.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "reports/"
    filter_suffix       = ".csv"
  }
  depends_on = [aws_lambda_permission.mailer_invoke_permission]
}

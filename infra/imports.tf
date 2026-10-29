# Do not apply until CloudFormation has retained and released all imported resources.
import {
  to = aws_cognito_identity_provider.google_identity_provider
  id = "us-east-1_Mqco1qka2:Google"
}

import {
  to = aws_cognito_managed_login_branding.managed_login_branding
  id = "us-east-1_Mqco1qka2,b6fc347c-3287-4715-97ab-c3ace231bea5"
}

import {
  to = aws_cognito_user_pool.user_pool
  id = "us-east-1_Mqco1qka2"
}

import {
  to = aws_cognito_user_pool_client.user_pool_client
  id = "us-east-1_Mqco1qka2/1r45prm239cn18b3felrql6s2g"
}

import {
  to = aws_cognito_user_pool_domain.user_pool_domain
  id = "peach738-auth"
}

import {
  to = aws_vpc_security_group_ingress_rule.database_ingress_from_report_builder
  id = "sgr-0983f67b6d67c9975"
}

import {
  to = aws_lambda_permission.mailer_invoke_permission
  id = "peach-report-mailer/peach-reports-MailerInvokePermission-p5TSfT9KnVDF"
}

import {
  to = aws_lambda_function.report_builder_function
  id = "peach-report-builder"
}

import {
  to = aws_cloudwatch_log_group.report_builder_log_group
  id = "/aws/lambda/peach-report-builder"
}

import {
  to = aws_iam_role.report_builder_role
  id = "peach-reports-ReportBuilderRole-fgH98bfpuOcI"
}

import {
  to = aws_iam_role_policy.report_builder_role
  id = "peach-reports-ReportBuilderRole-fgH98bfpuOcI:ReportBuilderRuntime"
}

import {
  to = aws_security_group.report_builder_security_group
  id = "sg-093cb177e9126c160"
}

import {
  to = aws_lambda_function.report_mailer_function
  id = "peach-report-mailer"
}

import {
  to = aws_cloudwatch_log_group.report_mailer_log_group
  id = "/aws/lambda/peach-report-mailer"
}

import {
  to = aws_iam_role.report_mailer_role
  id = "peach-reports-ReportMailerRole-mio3Ev1tiq9c"
}

import {
  to = aws_iam_role_policy.report_mailer_role
  id = "peach-reports-ReportMailerRole-mio3Ev1tiq9c:ReportMailerRuntime"
}

import {
  to = aws_lambda_event_source_mapping.report_queue_event_source
  id = "e97c0e85-be7b-4ad2-95db-8018db33207d"
}

import {
  to = aws_sqs_queue_policy.requests
  id = "https://sqs.eu-north-1.amazonaws.com/505464394565/peach-report-requests"
}

import {
  to = aws_sqs_queue_policy.dlq
  id = "https://sqs.eu-north-1.amazonaws.com/505464394565/peach-report-requests-dlq"
}

import {
  to = aws_sqs_queue.report_requests_dlq
  id = "https://sqs.eu-north-1.amazonaws.com/505464394565/peach-report-requests-dlq"
}

import {
  to = aws_sqs_queue.report_requests_queue
  id = "https://sqs.eu-north-1.amazonaws.com/505464394565/peach-report-requests"
}

import {
  to = aws_s3_bucket.reports_bucket
  id = "peach-reports-505464394565"
}

import {
  to = aws_s3_bucket_policy.reports_bucket_policy
  id = "peach-reports-505464394565"
}

import {
  to = aws_vpc_endpoint.s3_gateway_endpoint
  id = "vpce-0c4bedef671c0122f"
}

import {
  to = aws_iam_role.scheduler_role
  id = "peach-reports-SchedulerRole-BSH6JWvXp1h3"
}

import {
  to = aws_iam_role_policy.scheduler_role
  id = "peach-reports-SchedulerRole-BSH6JWvXp1h3:SendWeeklyReportCommand"
}

import {
  to = aws_scheduler_schedule.weekly_report_schedule
  id = "default/peach-weekly-reports"
}

import {
  to = aws_s3_bucket_versioning.reports
  id = "peach-reports-505464394565"
}

import {
  to = aws_s3_bucket_server_side_encryption_configuration.reports
  id = "peach-reports-505464394565"
}

import {
  to = aws_s3_bucket_ownership_controls.reports
  id = "peach-reports-505464394565"
}

import {
  to = aws_s3_bucket_public_access_block.reports
  id = "peach-reports-505464394565"
}

import {
  to = aws_s3_bucket_lifecycle_configuration.reports
  id = "peach-reports-505464394565"
}

import {
  to = aws_s3_bucket_notification.reports
  id = "peach-reports-505464394565"
}

# Existing parser resources; provider aws.ai targets account 985040259102.
import {
  to = aws_cloudwatch_log_group.parser_log_group[0]
  id = "/aws/lambda/peach-agenda-parser"
}

import {
  to = aws_iam_role.parser_role[0]
  id = "peach-ai-sonnet-ParserRole-bKIYeXFKNxBU"
}

import {
  to = aws_iam_role_policy.parser_role[0]
  id = "peach-ai-sonnet-ParserRole-bKIYeXFKNxBU:AgendaParserRuntime"
}

import {
  to = aws_lambda_function.parser_function[0]
  id = "peach-agenda-parser"
}

import {
  to = aws_lambda_function_url.parser_url[0]
  id = "peach-agenda-parser"
}

import {
  to = aws_lambda_permission.parser_url_permission[0]
  id = "peach-agenda-parser/peach-ai-sonnet-ParserUrlPermission-bFFWkCUOiXm4"
}

import {
  to = aws_lambda_permission.parser_invoke_permission[0]
  id = "peach-agenda-parser/peach-ai-sonnet-ParserInvokePermission-dplwUS0Qp72x"
}

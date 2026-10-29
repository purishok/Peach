output "user_pool_id" {
  value = aws_cognito_user_pool.user_pool.id
}

output "user_pool_client_id" {
  value = aws_cognito_user_pool_client.user_pool_client.id
}

output "cognito_domain" {
  value = "https://${var.cognito_domain_prefix}.auth.${var.auth_region}.amazoncognito.com"
}

output "cognito_authority" {
  value = "https://cognito-idp.${var.auth_region}.amazonaws.com/${aws_cognito_user_pool.user_pool.id}"
}

output "application_callback_url" {
  value = var.application_callback_url
}

output "application_logout_url" {
  value = var.application_logout_url
}

output "google_authorized_java_script_origin" {
  value = "https://${var.cognito_domain_prefix}.auth.${var.auth_region}.amazoncognito.com"
}

output "google_authorized_redirect_uri" {
  value = "https://${var.cognito_domain_prefix}.auth.${var.auth_region}.amazoncognito.com/oauth2/idpresponse"
}

output "reports_bucket_name" {
  value = aws_s3_bucket.reports_bucket.bucket
}

output "report_requests_queue_url" {
  value = aws_sqs_queue.report_requests_queue.url
}

output "report_requests_queue_arn" {
  value = aws_sqs_queue.report_requests_queue.arn
}

output "report_requests_dlq_url" {
  value = aws_sqs_queue.report_requests_dlq.url
}

output "report_builder_function_name" {
  value = aws_lambda_function.report_builder_function.function_name
}

output "report_mailer_function_name" {
  value = aws_lambda_function.report_mailer_function.function_name
}

output "weekly_schedule_name" {
  value = aws_scheduler_schedule.weekly_report_schedule.name
}

output "builder_log_group_name" {
  value = aws_cloudwatch_log_group.report_builder_log_group.name
}

output "mailer_log_group_name" {
  value = aws_cloudwatch_log_group.report_mailer_log_group.name
}

output "parser_url" {
  value = try(aws_lambda_function_url.parser_url[0].function_url, "")
}

output "parser_function_name" {
  value = try(aws_lambda_function.parser_function[0].function_name, "")
}

output "cognito_region" {
  value = var.auth_region
}

output "ses_dkim_tokens" {
  value = try(aws_sesv2_email_identity.ses_email_identity[0].dkim_signing_attributes[0].tokens, [])
}

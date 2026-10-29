variable "application_callback_url" {
  type        = string
  description = "Exact HTTPS callback URL for the deployed frontend."
}

variable "application_logout_url" {
  type        = string
  description = "Exact HTTPS URL Cognito may return to after logout."
}

variable "architecture" {
  type        = string
  description = "Architecture"
  default     = "arm64"
  validation {
    condition     = contains(["arm64", "x86_64"], var.architecture)
    error_message = "architecture must be arm64 or x86_64."
  }
}

variable "auth_region" {
  type    = string
  default = "us-east-1"
}

variable "bedrock_region" {
  type        = string
  description = "BedrockRegion"
  default     = "us-east-1"
}

variable "builder_memory_size" {
  type        = number
  description = "BuilderMemorySize"
  default     = 512
  validation {
    condition     = var.builder_memory_size >= 128 && var.builder_memory_size <= 10240 && floor(var.builder_memory_size) == var.builder_memory_size
    error_message = "builder_memory_size must be an integer from 128 to 10240."
  }
}

variable "cognito_domain_prefix" {
  type        = string
  description = "Globally unique prefix for the Cognito managed-login domain."
}

variable "create_ses_email_identity" {
  type        = bool
  description = "Create an SES domain identity for SesIdentityName when one is not already managed."
  default     = false
}

variable "database_secret_arn" {
  type        = string
  description = "Existing Secrets Manager ARN containing database_url; state contains the resolved value."
}

variable "database_security_group_id" {
  type        = string
  description = "DatabaseSecurityGroupId"
}

variable "failure_test_week" {
  type        = string
  description = "Test-only poison week; keep empty during normal operation."
  default     = ""
}

variable "google_client_id" {
  type        = string
  description = "Google OAuth 2.0 web application client ID."
}

variable "google_client_secret" {
  type        = string
  description = "Google OAuth 2.0 web application client secret."
  sensitive   = true
}

variable "local_callback_url" {
  type        = string
  description = "LocalCallbackUrl"
  default     = "http://localhost:3000/auth/callback"
}

variable "local_logout_url" {
  type        = string
  description = "LocalLogoutUrl"
  default     = "http://localhost:3000/"
}

variable "log_retention_days" {
  type        = number
  description = "LogRetentionDays"
  default     = 14
}

variable "parser_api" {
  type        = string
  description = "ParserApi"
  default     = "messages"
  validation {
    condition     = contains(["messages", "converse"], var.parser_api)
    error_message = "parser_api must be messages or converse."
  }
}

variable "parser_image_uri" {
  type        = string
  description = "Lambda container image in this stack's region."
  default     = null
}

variable "parser_model" {
  type        = string
  description = "ParserModel"
  default     = "anthropic.claude-opus-5-5"
}

variable "project_name" {
  type        = string
  description = "ProjectName"
  default     = "peach"
  validation {
    condition     = can(regex("^[a-zA-Z0-9-]+$", var.project_name))
    error_message = "project_name must contain only letters, digits and hyphens."
  }
}

variable "region" {
  type    = string
  default = "eu-north-1"
}

variable "report_recipient_emails" {
  type        = string
  description = "Comma-separated recipients; sandbox recipients must be verified."
  sensitive   = true
}

variable "report_sender_email" {
  type        = string
  description = "Existing verified SES sender, normally reports@verified-domain."
}

variable "reports_image_uri" {
  type        = string
  description = "Lambda-compatible backend container image URI."
}

variable "reserved_concurrency" {
  type        = number
  description = "ReservedConcurrency"
  default     = 2
  validation {
    condition     = var.reserved_concurrency >= 0 && var.reserved_concurrency <= 1000 && floor(var.reserved_concurrency) == var.reserved_concurrency
    error_message = "reserved_concurrency must be an integer from 0 to 1000; 0 preserves the old unreserved setting."
  }
}

variable "route_table_ids" {
  type        = list(string)
  description = "RouteTableIds"
}

variable "ses_identity_name" {
  type        = string
  description = "Verified SES email address or domain used to scope send permissions."
}

variable "site_origin" {
  type        = string
  description = "Exact HTTPS origin of the deployed frontend."
  default     = "https://dqvalqr0apze.cloudfront.net"
}

variable "subnet_ids" {
  type        = list(string)
  description = "SubnetIds"
}

variable "vpc_id" {
  type        = string
  description = "VpcId"
}

variable "enable_ai" {
  type        = bool
  description = "Manage the existing parser in the separate AI account. Disabling after import plans its removal."
  default     = false
}

variable "default_tags" {
  type        = map(string)
  description = "Additional default tags. Existing PROJECT_NAME tags are preserved explicitly during adoption."
  default     = {}
}
variable "ai_region" {
  type    = string
  default = "eu-north-1"
}
variable "ai_profile" {
  type        = string
  description = "Local read-only inventory profile; null in HCP, which uses dynamic credentials."
  default     = null
}
variable "ai_account_id" {
  type    = string
  default = "985040259102"
}

variable "tfc_aws_dynamic_credentials" {
  description = "Injected by HCP for the default account and the AI credential alias."
  type = object({
    default = object({ shared_config_file = string })
    aliases = map(object({ shared_config_file = string }))
  })
  default = null
}

variable "account_id" {
  type    = string
  default = "505464394565"
}

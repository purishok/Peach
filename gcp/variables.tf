variable "project_id" {
  type        = string
  description = "Dedicated, billing-enabled Google Cloud project for Lab 9."

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "Use a valid Google Cloud project ID."
  }
}

variable "terraform_service_account" {
  type        = string
  description = "Email of the bootstrap-created Terraform identity to impersonate."
}

variable "backend_image" {
  type        = string
  description = "Digest-pinned image in the Peach Artifact Registry repository. Leave null for the initial registry apply."
  default     = null
}

variable "database_running" {
  type        = bool
  description = "Whether Cloud SQL is running. Storage is billed while stopped."
  default     = true
}

variable "cognito_pool_id" {
  type        = string
  description = "Existing AWS Cognito pool ID (including region). Required when deploying the API."
  default     = ""
}

variable "cognito_client_id" {
  type        = string
  description = "Public Cognito app client ID. Required when deploying the API."
  default     = ""
}

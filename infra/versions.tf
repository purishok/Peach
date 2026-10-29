terraform {
  required_version = ">= 1.10, < 2.0"

  # Set TF_CLOUD_ORGANIZATION and TF_WORKSPACE=peach-dev in your shell
  # and in HCP workspace environment variables. Never store an API token here.
  cloud {
    organization = "Pitch_organisation"
    workspaces { name = "peach-dev" }
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region              = var.region
  allowed_account_ids = [var.account_id]
  shared_config_files = var.tfc_aws_dynamic_credentials == null ? null : [var.tfc_aws_dynamic_credentials.default.shared_config_file]
  default_tags {
    tags = var.default_tags
  }
}

provider "aws" {
  alias               = "auth"
  region              = var.auth_region
  allowed_account_ids = [var.account_id]
  shared_config_files = var.tfc_aws_dynamic_credentials == null ? null : [var.tfc_aws_dynamic_credentials.default.shared_config_file]
  default_tags {
    tags = var.default_tags
  }
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

data "aws_secretsmanager_secret_version" "database" {
  secret_id = var.database_secret_arn
}

# HCP injects the AI account role through the tagged dynamic credential config.
# Keep ai_profile null remotely; a local named profile is only for migration reads.
provider "aws" {
  alias               = "ai"
  region              = var.ai_region
  profile             = var.ai_profile
  shared_config_files = var.tfc_aws_dynamic_credentials == null ? null : [var.tfc_aws_dynamic_credentials.aliases["AI"].shared_config_file]
  allowed_account_ids = var.enable_ai ? [var.ai_account_id] : null
  default_tags { tags = var.default_tags }
}

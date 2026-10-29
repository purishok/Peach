# Migrated from cognito.yaml. Existing physical names are preserved.

resource "aws_cognito_user_pool" "user_pool" {
  tags                     = { PROJECT_NAME = var.project_name }
  provider                 = aws.auth
  name                     = "${var.project_name}-users"
  user_pool_tier           = "ESSENTIALS"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  username_configuration { case_sensitive = false }
  admin_create_user_config { allow_admin_create_user_only = false }
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }
  password_policy {
    minimum_length                   = 8
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = false
    require_uppercase                = true
    temporary_password_validity_days = 7
  }
  schema {
    name                = "email"
    attribute_data_type = "String"
    mutable             = true
    required            = true
    string_attribute_constraints {
      min_length = "0"
      max_length = "2048"
    }
  }
  lifecycle { prevent_destroy = true }
}

resource "aws_cognito_identity_provider" "google_identity_provider" {
  provider      = aws.auth
  user_pool_id  = aws_cognito_user_pool.user_pool.id
  provider_name = "Google"
  provider_type = "Google"
  provider_details = {
    client_id                     = var.google_client_id
    client_secret                 = var.google_client_secret
    authorize_scopes              = "openid email profile"
    attributes_url                = "https://people.googleapis.com/v1/people/me?personFields="
    attributes_url_add_attributes = "true"
    authorize_url                 = "https://accounts.google.com/o/oauth2/v2/auth"
    oidc_issuer                   = "https://accounts.google.com"
    token_request_method          = "POST"
    token_url                     = "https://www.googleapis.com/oauth2/v4/token"
  }
  attribute_mapping = { "email" = "email", "email_verified" = "email_verified", "username" = "sub" }
}

resource "aws_cognito_user_pool_client" "user_pool_client" {
  provider                             = aws.auth
  user_pool_id                         = aws_cognito_user_pool.user_pool.id
  name                                 = "${var.project_name}-browser"
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  supported_identity_providers         = ["COGNITO", "Google"]
  callback_urls                        = [var.application_callback_url, var.local_callback_url]
  logout_urls                          = [var.application_logout_url, var.local_logout_url]
  prevent_user_existence_errors        = "ENABLED"
  enable_token_revocation              = true
  refresh_token_validity               = 30
  access_token_validity                = 1
  id_token_validity                    = 1
  read_attributes                      = ["email", "email_verified", "name"]
  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }
  # Preserve AWS's existing implicit one-hour access/ID token lifetime explicitly.
  depends_on = [aws_cognito_identity_provider.google_identity_provider]
}

resource "aws_cognito_user_pool_domain" "user_pool_domain" {
  provider              = aws.auth
  domain                = var.cognito_domain_prefix
  user_pool_id          = aws_cognito_user_pool.user_pool.id
  managed_login_version = 2
}

resource "aws_cognito_managed_login_branding" "managed_login_branding" {
  provider                    = aws.auth
  user_pool_id                = aws_cognito_user_pool.user_pool.id
  client_id                   = aws_cognito_user_pool_client.user_pool_client.id
  use_cognito_provided_values = true
  depends_on                  = [aws_cognito_user_pool_domain.user_pool_domain]
}

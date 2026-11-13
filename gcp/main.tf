locals {
  region   = "us-central1"
  services = var.backend_image == null ? {} : { api = var.backend_image }
}

resource "google_project_service" "api" {
  for_each = toset([
    "artifactregistry.googleapis.com",
    "firebase.googleapis.com",
    "firebasehosting.googleapis.com",
    "iam.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "sqladmin.googleapis.com",
  ])

  service            = each.key
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "backend" {
  location      = local.region
  repository_id = "peach"
  format        = "DOCKER"

  depends_on = [google_project_service.api["artifactregistry.googleapis.com"]]
}

data "google_service_account" "api" {
  for_each   = local.services
  account_id = "peach-run"
}

resource "google_sql_database_instance" "peach" {
  for_each            = local.services
  name                = "peach-lab9"
  region              = local.region
  database_version    = "POSTGRES_17"
  deletion_protection = false

  settings {
    edition           = "ENTERPRISE"
    tier              = "db-f1-micro"
    availability_type = "ZONAL"
    disk_size         = 10
    disk_type         = "PD_SSD"
    disk_autoresize   = false
    activation_policy = var.database_running ? "ALWAYS" : "NEVER"

    ip_configuration {
      ipv4_enabled = true
      ssl_mode     = "ENCRYPTED_ONLY"
    }
  }

  depends_on = [google_project_service.api["sqladmin.googleapis.com"]]
}

resource "google_sql_database" "peach" {
  for_each = local.services
  name     = "peach"
  instance = google_sql_database_instance.peach[each.key].name
}

resource "random_password" "database" {
  for_each = local.services
  length   = 40
  special  = false
}

resource "google_sql_user" "peach" {
  for_each = local.services
  name     = "peach"
  instance = google_sql_database_instance.peach[each.key].name
  password = random_password.database[each.key].result
}

resource "google_secret_manager_secret" "database_url" {
  for_each  = local.services
  secret_id = "peach-database-url"

  replication {
    auto {}
  }

  depends_on = [google_project_service.api["secretmanager.googleapis.com"]]
}

resource "google_secret_manager_secret_version" "database_url" {
  for_each = local.services
  secret   = google_secret_manager_secret.database_url[each.key].id
  # Build this from the generated password and mounted socket path. Keep the
  # URL percent-free so it can also pass through Alembic's INI interpolation.
  secret_data = "postgresql+asyncpg://${google_sql_user.peach[each.key].name}:${random_password.database[each.key].result}@/${google_sql_database.peach[each.key].name}?host=/cloudsql/${google_sql_database_instance.peach[each.key].connection_name}"
}

resource "google_secret_manager_secret_iam_member" "api" {
  for_each  = local.services
  secret_id = google_secret_manager_secret.database_url[each.key].id
  role      = "roles/secretmanager.secretAccessor"
  member    = data.google_service_account.api[each.key].member
}

resource "google_cloud_run_v2_service" "api" {
  for_each             = local.services
  name                 = "peach-api"
  location             = local.region
  deletion_protection  = false
  invoker_iam_disabled = true

  lifecycle {
    precondition {
      condition     = startswith(each.value, "${local.region}-docker.pkg.dev/${var.project_id}/peach/backend@sha256:") && can(regex("@sha256:[a-f0-9]{64}$", each.value))
      error_message = "Use the pushed backend digest from the lab's Artifact Registry repository."
    }
    precondition {
      condition     = can(regex("^[a-z]{2}(-[a-z0-9]+)+-[0-9]+_[a-zA-Z0-9]+$", var.cognito_pool_id)) && can(regex("^[a-zA-Z0-9]+$", var.cognito_client_id))
      error_message = "Configure the existing Cognito pool and app client before exposing the API."
    }
  }

  template {
    service_account       = data.google_service_account.api[each.key].email
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"

    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.peach[each.key].connection_name]
      }
    }

    containers {
      image = each.value

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = true
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      env {
        name  = "APP_ENV"
        value = "production"
      }
      env {
        name  = "DB_POOLING"
        value = "false"
      }
      env {
        name  = "CORS_ORIGINS"
        value = ""
      }
      env {
        name  = "COGNITO_REGION"
        value = split("_", var.cognito_pool_id)[0]
      }
      env {
        name  = "COGNITO_USER_POOL_ID"
        value = var.cognito_pool_id
      }
      env {
        name  = "COGNITO_CLIENT_ID"
        value = var.cognito_client_id
      }
      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url[each.key].secret_id
            version = google_secret_manager_secret_version.database_url[each.key].version
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.api["run.googleapis.com"],
    google_secret_manager_secret_iam_member.api,
  ]
}

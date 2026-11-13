terraform {
  required_version = ">= 1.10, < 2.0"

  cloud {
    organization = "Pitch_organisation"
    workspaces { name = "peach-gcp-lab9" }
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7"
    }
  }
}

provider "google" {
  project                     = var.project_id
  region                      = "us-central1"
  impersonate_service_account = var.terraform_service_account
}

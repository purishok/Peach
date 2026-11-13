output "artifact_registry" {
  value = "${local.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.backend.repository_id}"
}

output "api_url" {
  value = try(google_cloud_run_v2_service.api["api"].uri, null)
}

output "hosting_url" {
  value = "https://${var.project_id}.web.app"
}

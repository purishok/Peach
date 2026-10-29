#!/usr/bin/env bash
# Legacy entry point: infrastructure is reviewed and applied by HCP Terraform.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "${TERRAFORM:-terraform}" -chdir="${ROOT}/infra" plan "$@"

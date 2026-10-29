#!/usr/bin/env python3
"""Refresh public application settings from the selected HCP workspace."""
import os
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = {
    "COGNITO_REGION": "cognito_region",
    "COGNITO_USER_POOL_ID": "user_pool_id",
    "COGNITO_CLIENT_ID": "user_pool_client_id",
    "COGNITO_DOMAIN": "cognito_domain",
    "COGNITO_AUTHORITY": "cognito_authority",
    "COGNITO_REDIRECT_URI": "application_callback_url",
    "COGNITO_LOGOUT_URI": "application_logout_url",
    "PARSER_URL": "parser_url",
}

def main():
    values = {}
    for key, output in OUTPUTS.items():
        value = subprocess.check_output(
            [os.environ.get("TERRAFORM", "terraform"), f"-chdir={ROOT / 'infra'}",
             "output", "-raw", output], text=True,
        ).strip()
        if value or key != "PARSER_URL":
            values[key] = value
    path = ROOT / ".env"
    lines = path.read_text().splitlines() if path.exists() else []
    lines = [line for line in lines if line.partition("=")[0] not in values]
    lines.extend(f"{key}={shlex.quote(value)}" for key, value in values.items())
    # Keep any pre-existing credentials private as well.
    temporary = path.with_name(".env.terraform-tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write("\n".join(lines) + "\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    print("Public Terraform outputs saved to .env")

if __name__ == "__main__":
    main()

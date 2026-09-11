"""Caller-selected S3 backend; no backend fallback, migration or second lock."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from iaas_automation.common.errors import ValidationError, require
from iaas_automation.common.io import write_text
from .process import ProcessResult, run_protected


S3_ENV = {"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
          "AWS_SHARED_CREDENTIALS_FILE", "AWS_SHARED_CONFIG_FILE", "AWS_PROFILE",
          "AWS_CA_BUNDLE", "AWS_WEB_IDENTITY_TOKEN_FILE", "AWS_ROLE_ARN", "AWS_ROLE_SESSION_NAME"}
PVE_ENV = {"TF_VAR_pve_endpoint", "TF_VAR_pve_api_username", "TF_VAR_pve_api_token_id",
           "TF_VAR_pve_api_token_secret", "TF_VAR_pve_insecure", "TF_VAR_pve_ssh_username",
           "TF_VAR_pve_ssh_private_key", "IAAS_PVE_SSH_TIMEOUT_SECONDS"}


@dataclass(frozen=True)
class S3Backend:
    config: dict[str, Any]
    workspace: str

    @classmethod
    def load(cls, path: Path) -> S3Backend:
        try:
            document = json.loads(path.read_text())
        except (OSError, ValueError):
            raise ValidationError("caller S3 configuration must be readable JSON") from None
        require(isinstance(document, dict) and set(document) == {"workspace", "config"},
                "S3 configuration requires workspace and config")
        workspace, config = document["workspace"], document["config"]
        require(isinstance(workspace, str) and re.fullmatch(r"[A-Za-z0-9_-]+", workspace), "invalid workspace")
        require(isinstance(config, dict), "S3 config must be an object")
        for name in ("bucket", "key", "region"):
            require(isinstance(config.get(name), str) and bool(config[name]), "S3 bucket, key and region are required")
        require(config.get("use_lockfile") is True, "S3 native use_lockfile must be true")
        if workspace != "default":
            require(isinstance(config.get("workspace_key_prefix"), str), "non-default workspace requires explicit key prefix")
        require(not {"access_key", "secret_key", "token", "dynamodb_table"} & config.keys(),
                "inject credentials externally; only native S3 locking is supported")
        return cls(config, workspace)

    def identity(self) -> dict[str, Any]:
        """Persist in protected plan metadata, never ordinary public logs."""
        return {"bucket": self.config["bucket"], "key": self.config["key"],
                "region": self.config["region"], "endpoints": self.config.get("endpoints", {}),
                "endpoint": self.config.get("endpoint"), "workspace": self.workspace,
                "workspace_key_prefix": self.config.get("workspace_key_prefix", "env:")}

    def initialize(self, root: Path, environ: dict[str, str], recovery: Path, tofu: str = "tofu",
                   *, plugin_dir: Path | None = None) -> ProcessResult:
        # Native override semantics replace the caller root's backend declaration
        # only in the new task copy, using the explicitly supplied S3 selection.
        # No existing state or backend metadata is copied/migrated into this root.
        declaration = root / "zz_iaas_backend_override.tf.json"
        require(not declaration.exists(), "reserved runtime backend file already exists")
        require(not (root / ".terraform/terraform.tfstate").exists() and not (root / "terraform.tfstate").exists(),
                "state initialization requires a fresh task root; migration is not supported")
        write_text(declaration, json.dumps({"terraform": {"backend": {"s3": self.config}}}), secure=True)
        mirror = plugin_dir if plugin_dir is not None else root / ".iaas-provider-mirror"
        mirror.mkdir(parents=True, exist_ok=True, mode=0o700)
        environment = {**environ, "TF_WORKSPACE": self.workspace, "TF_IN_AUTOMATION": "1", "TF_INPUT": "0"}
        return run_protected([tofu, "init", "-input=false", "-lockfile=readonly", "-get=false", f"-plugin-dir={mirror}"], cwd=root,
                             environ=environment, capture=recovery / "backend-init.raw")

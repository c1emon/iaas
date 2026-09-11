"""Discover the selected operation's inputs without reading unrelated secrets."""

from __future__ import annotations

import json
from pathlib import Path

from iaas_automation.common.errors import require
from iaas_automation.runtime_config import SelectedConfig, SourceReader, load_environment
from iaas_automation.runtime_config.compile import compile_documents
from .operations import operation_for


def load_operation(entry: Path, component: str, operation: str, scenario: str | None,
                   reader: SourceReader) -> SelectedConfig:
    effects = operation_for(component, operation)
    metadata = load_environment(entry, component, scenario, reader, input_names=set(), file_names=set())
    inputs: set[str] | None = None
    files: set[str] = set()
    if operation == "apply-saved-plan":
        inputs = set()
        files |= {"backend", "ssh_key", "known_hosts"}
    elif operation in {"prepare-dependencies", "plan", "prepare-plan"}:
        if operation == "prepare-dependencies":
            inputs = set()
        root = metadata.options.get("root", {})
        require(isinstance(root, dict) and isinstance(root.get("files"), dict), "explicit root files are required")
        files |= set(root["files"].values())
        if effects.state:
            files.add("backend")
            if "dependencies" in metadata.file_paths:
                files.add("dependencies")
    elif effects.network and component in {"opnsense", "switch"}:
        inputs = set()
        files.add("inventory")
        if component == "opnsense":
            files.add("request")
        else:
            files.add("known_hosts")
    elif effects.network and component == "k3s":
        files |= {"ssh_key", "known_hosts"}
        if operation in {"preflight", "deploy", "upgrade"}:
            files.add("runtime_secrets")
        if operation == "upgrade":
            files.add("observed_versions")
    elif effects.network and component == "foundation":
        files |= set(metadata.options.get("ca_files", {}).values())
    if effects.state:
        # Optional standard AWS file channels are mapped explicitly by alias.
        files |= {name for name in ("aws_credentials", "aws_config", "aws_ca", "aws_web_identity")
                  if name in metadata.file_paths}
    return load_environment(entry, component, scenario, reader, input_names=inputs, file_names=files)


def rendering_credentials(selected: SelectedConfig, operation: str) -> tuple[str, ...]:
    if selected.component != "pve" or operation not in {"plan", "prepare-plan"}:
        return ()
    tfvars = json.loads(compile_documents(selected)["pve.tfvars.json"])
    return tuple(sorted({user[field] for user in tfvars["cluster"]["automation"]["cloud_init"]["users"]
                         for field in ("password_env", "public_key_env")}))

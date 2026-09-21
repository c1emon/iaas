"""Discover the selected operation's inputs without reading unrelated secrets."""

from __future__ import annotations

import json
from pathlib import Path
import re

from iaas_automation.common.errors import require
from iaas_automation.runtime_config import SelectedConfig, SourceReader, load_environment
from iaas_automation.runtime_config.compile import compile_documents
from iaas_automation.opnsense_validation import RESOURCE_FILES, validate_documents
from .operations import operation_for
from iaas_automation.opnsense_workflow.contracts import load_candidate


OPNSENSE_WORKFLOW_OPERATIONS = {"read", "plan", "apply", "verify"}
_OPNSENSE_APPLY_OPTIONS = {"candidate_sha256", "execution_id", "activation_check"}
_OPNSENSE_READ_OPTIONS = {"include_system"}


def _declared_input_names(entry: Path, component: str, scenario: str | None,
                          reader: SourceReader) -> set[str]:
    """Return declared names without resolving or reading their source files."""
    document = reader.document(entry)
    components = document.get("components", {})
    selected = components.get(component, {}) if isinstance(components, dict) else {}
    if scenario is not None:
        scenarios = document.get("scenarios", {})
        replacement = scenarios.get(scenario, {}) if isinstance(scenarios, dict) else {}
        if isinstance(replacement, dict) and component in replacement:
            selected = replacement[component]
    inputs = selected.get("inputs", {}) if isinstance(selected, dict) else {}
    return set(inputs) if isinstance(inputs, dict) else set()


def _validate_opnsense_request(selected: SelectedConfig, reader: SourceReader) -> None:
    """Validate request structure before any credential preparation."""
    logical = selected.file_paths["request"]
    request_document = reader.document(logical)
    from iaas_automation.opnsense_workflow.contracts import request

    request(request_document)


def _validate_opnsense_options(selected: SelectedConfig, operation: str) -> None:
    if operation == "read":
        require(set(selected.options) <= _OPNSENSE_READ_OPTIONS,
                "OPNsense read option must be include_system")
        require(type(selected.options.get("include_system", False)) is bool,
                "OPNsense read include_system must be a boolean")
        return
    if operation != "apply":
        require(not selected.options, "OPNsense workflow read, plan and verify do not accept options")
        return
    options = selected.options
    option_names = set(options)
    require(option_names == _OPNSENSE_APPLY_OPTIONS
            or option_names == _OPNSENSE_APPLY_OPTIONS | {"check_mode"},
            "OPNsense apply options must be candidate_sha256, execution_id and activation_check")
    require(isinstance(options["candidate_sha256"], str)
            and re.fullmatch(r"[0-9a-f]{64}", options["candidate_sha256"]) is not None,
            "OPNsense apply candidate_sha256 must be a lowercase SHA-256")
    require(isinstance(options["execution_id"], str)
            and re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", options["execution_id"]) is not None,
            "OPNsense apply execution_id must be a bounded identifier")
    require(type(options.get("check_mode", False)) is bool,
            "OPNsense apply check_mode must be a boolean")
    check = options["activation_check"]
    require(isinstance(check, dict)
            and set(check) == {"target", "candidate_sha256", "execution_id", "checked_no_pending", "serialized"},
            "OPNsense apply activation_check is incomplete")
    require(isinstance(check["target"], dict)
            and check["candidate_sha256"] == options["candidate_sha256"]
            and check["execution_id"] == options["execution_id"]
            and check["checked_no_pending"] is True and check["serialized"] is True,
            "OPNsense apply activation_check is not bound to this execution")


def _validate_opnsense_candidate(selected: SelectedConfig, operation: str) -> None:
    if operation not in {"apply", "verify"}:
        return
    options = selected.options if operation == "apply" else {}
    reviewed = options.get("candidate_sha256") if operation == "apply" else None
    load_candidate(selected.files["candidate"], reviewed=reviewed)


def load_operation(entry: Path, component: str, operation: str, scenario: str | None,
                   reader: SourceReader) -> SelectedConfig:
    effects = operation_for(component, operation)
    metadata = load_environment(entry, component, scenario, reader, input_names=set(), file_names=set())
    inputs: set[str] | None = None
    files: set[str] = set()
    if component == "opnsense" and operation in OPNSENSE_WORKFLOW_OPERATIONS:
        # The workflow has its own candidate/recovery contract.  Keep this
        # selection layer responsible only for transporting the explicit
        # aliases so discovery never reads unrelated desired files.  The
        # workflow validates request.selection and selects declarations from
        # the loaded standard resource documents for plan.
        inputs = set()
        files.add("inventory")
        if operation == "read":
            files.add("request")
        elif operation == "plan":
            all_declared = _declared_input_names(entry, component, scenario, reader)
            require(all_declared <= set(RESOURCE_FILES), "unsupported OPNsense input")
            declared = all_declared
            require(not (declared and "recovery" in metadata.file_paths),
                    "desired inputs and recovery are mutually exclusive")
            # Plan carries the complete declared candidate context; the
            # request selection controls the execution set in the workflow.
            inputs = declared
            files.add("request")
            if "recovery" in metadata.file_paths:
                files.add("recovery")
        else:
            files.add("candidate")
    elif operation == "apply-saved-plan":
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
    selected = load_environment(entry, component, scenario, reader, input_names=inputs, file_names=files)
    if component == "opnsense" and operation in OPNSENSE_WORKFLOW_OPERATIONS:
        _validate_opnsense_options(selected, operation)
        if operation == "plan" and "recovery" not in selected.files:
            validate_documents(selected.documents)
        _validate_opnsense_candidate(selected, operation)
        if operation in {"read", "plan"}:
            _validate_opnsense_request(selected, reader)
    return selected


def rendering_credentials(selected: SelectedConfig, operation: str) -> tuple[str, ...]:
    if selected.component != "pve" or operation not in {"plan", "prepare-plan"}:
        return ()
    tfvars = json.loads(compile_documents(selected)["pve.tfvars.json"])
    return tuple(sorted({user[field] for user in tfvars["cluster"]["automation"]["cloud_init"]["users"]
                         for field in ("password_env", "public_key_env")}))

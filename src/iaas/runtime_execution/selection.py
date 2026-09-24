"""Discover the selected operation's inputs without reading unrelated secrets."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, cast

from iaas.common.errors import require
from iaas.runtime_config import InputRequired, SelectedConfig, SourceReader, load_environment
from iaas.runtime_config.compile import compile_documents
from iaas.opnsense_validation import RESOURCE_FILES, validate_documents
from .operations import operation_for
from iaas.opnsense_workflow.contracts import load_candidate


OPNSENSE_WORKFLOW_OPERATIONS = {"read", "plan", "apply", "verify"}
_OPNSENSE_APPLY_OPTIONS = {"candidate_sha256", "execution_id", "activation_check"}
_OPNSENSE_READ_OPTIONS = {"include_system"}
PVE_WORKFLOW_OPERATIONS = {"read", "plan", "apply", "verify"}
_PVE_TEMPLATE_INPUTS = {"request", "publish", "cleanup", "retire"}
_IMAGE_INPUTS = {"request", "build", "test", "artifact"}
_PVE_TEMPLATE_FILE_INPUTS = {
    "read": {"journal", "api_ca"},
    "plan": {"artifact", "publish_request", "api_ca"},
    "apply": {"preview", "template_preview", "execution_admission", "artifact_locator", "api_ca"},
    "verify": {"result", "template_result", "preview", "template_preview"},
}
_IMAGE_FILE_INPUTS = {
    "read": {"execution_dir"}, "verify": {"artifact"}, "clean": {"execution_dir"},
}


def _map_image_external_paths(selected: SelectedConfig, operation: str) -> None:
    """Require and bind image directories that contain task or disk material."""
    mapping = selected.reader.mapping
    if mapping is None:
        return
    if operation == "test":
        document = selected.documents.get("test")
        if isinstance(document, dict) and isinstance(document.get("artifact_root"), str):
            logical = Path(document["artifact_root"]).resolve()
            supplied = mapping.get(str(logical))
            if supplied is None:
                raise InputRequired(logical)
            require(Path(supplied).is_dir(), "image artifact_root must be a supplied directory")
            document["artifact_root"] = supplied
    elif operation == "verify" and "artifact" in selected.files:
        logical_artifact = selected.file_paths["artifact"]
        logical_root = logical_artifact.resolve().parent
        supplied = mapping.get(str(logical_root))
        if supplied is None:
            raise InputRequired(logical_root)
        require(Path(supplied).is_dir(), "image artifact root must be a supplied directory")
        selected.options["artifact_root"] = supplied


def _map_pve_cleanup_directory(selected: SelectedConfig, operation: str) -> None:
    """Bind the publisher-owned recovery directory without changing its digest input."""
    request: dict[str, Any] | None = None
    if operation == "plan" and selected.options.get("action") == "cleanup":
        candidate = selected.documents.get("cleanup")
        if isinstance(candidate, dict):
            request = candidate
    elif operation == "apply":
        preview_logical = next((selected.file_paths[name] for name in ("preview", "template_preview")
                                if name in selected.file_paths), None)
        if preview_logical is not None:
            preview = selected.reader.document(preview_logical)
            if preview.get("action") == "cleanup" and isinstance(preview.get("fixed_input"), dict):
                request = preview["fixed_input"]
    if request is None:
        return
    logical_value = request.get("original_execution_dir")
    require(isinstance(logical_value, str),
            "cleanup original_execution_dir must be an absolute directory")
    logical_value = cast(str, logical_value)
    logical = Path(logical_value)
    require(logical.is_absolute(), "cleanup original_execution_dir must be an absolute directory")
    selected.files["original_execution_dir"] = selected.reader.locate(logical, allow_directory=True)
    selected.file_paths["original_execution_dir"] = logical


def _hydrate_pve_template_apply_options(selected: SelectedConfig) -> None:
    """Bind apply metadata to the selected preview and admission files.

    The files are the immutable apply inputs.  Keeping their derived digest and
    admission in ``options`` lets the component runtime use one interface for
    hand-authored and adapter-generated environments without asking callers to
    duplicate those values in YAML.
    """
    preview_names = [name for name in ("preview", "template_preview") if name in selected.file_paths]
    admission_path = selected.file_paths.get("execution_admission")
    if not preview_names or admission_path is None:
        return
    # The runtime consumes ``preview`` before its legacy alias
    # ``template_preview``.  If both are declared, require identical parsed
    # documents so the alias cannot hide a different apply binding.
    preview = selected.reader.document(selected.file_paths[preview_names[0]])
    for alias in preview_names[1:]:
        require(selected.reader.document(selected.file_paths[alias]) == preview,
                "pve-template apply preview aliases disagree")
    admission = selected.reader.document(admission_path)
    preview_digest = preview.get("preview_digest")
    action = preview.get("action")
    require(isinstance(preview_digest, str) and preview_digest,
            "pve-template apply preview is missing preview_digest")
    require(isinstance(action, str) and action,
            "pve-template apply preview is missing action")
    require(isinstance(admission, dict), "pve-template apply admission must contain a mapping")
    for name, value in (("action", action), ("preview_digest", preview_digest), ("admission", admission)):
        if name in selected.options:
            require(selected.options[name] == value,
                    f"pve-template apply {name} conflicts with selected file")
        else:
            selected.options[name] = value


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
    from iaas.opnsense_workflow.contracts import request

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
    elif component == "pve" and operation in PVE_WORKFLOW_OPERATIONS:
        # PVE lifecycle inputs intentionally differ by phase.  Read and plan
        # inspect the complete root and selected backend; apply consumes only
        # the caller's admission/target plus transferred companions; verify
        # consumes its retained result without initializing the backend.
        if operation in {"read", "plan"}:
            root = metadata.options.get("root", {})
            require(isinstance(root, dict) and isinstance(root.get("id"), str) and root["id"],
                    "explicit root id is required")
            files.add("backend")
            if operation == "plan":
                require(isinstance(root.get("files"), dict), "explicit root files are required")
                files |= set(root["files"].values())
                files.add("state_admission")
                files |= {name for name in ("template_records", "template_admission")
                          if name in metadata.file_paths}
                files |= {name for name in ("ssh_key", "known_hosts", "dependencies")
                          if name in metadata.file_paths}
            if operation == "read":
                inputs = set()
                files |= {"execution_result"} if "execution_result" in metadata.file_paths else set()
        elif operation == "apply":
            inputs = set()
            files.add("backend")
            files.add("execution_admission")
            files.add("state_admission")
            files |= {"template_admission"} if "template_admission" in metadata.file_paths else set()
            files |= {name for name in ("ssh_key", "known_hosts")
                      if name in metadata.file_paths}
        else:
            inputs = set()
            files |= {"execution_result"} if "execution_result" in metadata.file_paths else set()
    elif component == "pve-template" and operation in OPNSENSE_WORKFLOW_OPERATIONS:
        declared = _declared_input_names(entry, component, scenario, reader)
        require(declared <= _PVE_TEMPLATE_INPUTS, "unsupported pve-template input")
        inputs = declared
        files |= {name for name in _PVE_TEMPLATE_FILE_INPUTS.get(operation, set())
                  if name in metadata.file_paths}
    elif component == "image":
        declared = _declared_input_names(entry, component, scenario, reader)
        require(declared <= _IMAGE_INPUTS, "unsupported image input")
        inputs = declared
        files |= {name for name in _IMAGE_FILE_INPUTS.get(operation, set())
                  if name in metadata.file_paths}
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
    if component == "image":
        _map_image_external_paths(selected, operation)
    if component == "pve-template":
        if operation == "apply":
            _hydrate_pve_template_apply_options(selected)
        _map_pve_cleanup_directory(selected, operation)
    if component == "opnsense" and operation in OPNSENSE_WORKFLOW_OPERATIONS:
        _validate_opnsense_options(selected, operation)
        if operation == "plan" and "recovery" not in selected.files:
            validate_documents(selected.documents)
        _validate_opnsense_candidate(selected, operation)
        if operation in {"read", "plan"}:
            _validate_opnsense_request(selected, reader)
    return selected


def rendering_credentials(selected: SelectedConfig, operation: str) -> tuple[str, ...]:
    if selected.component != "pve" or operation != "plan":
        return ()
    tfvars = json.loads(compile_documents(selected)["pve.tfvars.json"])
    return tuple(sorted({user[field] for user in tfvars["cluster"]["automation"]["cloud_init"]["users"]
                         for field in ("password_env", "public_key_env")}))

"""Launcher-facing PVE template lifecycle runtime.

The controller owns only the request/receipt hand-off.  Long running work is
delegated to the node helper and is never replayed when the local process is
interrupted.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Mapping

from iaas_automation.common.errors import ValidationError, require
from iaas_automation.common.io import load_json, write_text
from iaas_automation.runtime_execution.execution import OperationFailed

from .contracts import (HELPER_PROTOCOL_VERSION, build_preview, canonical_digest,
                        validate_cleanup_preview, validate_preview, validate_recipe,
                        validate_request, validate_template_record)


HELPER_TIMEOUT_SECONDS = 30


def _document(selected: Any) -> dict[str, Any]:
    documents = getattr(selected, "documents", {})
    require(isinstance(documents, Mapping), "pve-template documents must be a mapping")
    recipe = documents.get("recipe", documents.get("template", documents.get("build")))
    require(isinstance(recipe, Mapping), "pve-template requires an independent recipe input")
    return dict(recipe)


def _path(selected: Any, *names: str) -> Path | None:
    files = getattr(selected, "files", {})
    for name in names:
        path = files.get(name) if isinstance(files, Mapping) else None
        if path is not None:
            return Path(path)
    return None


def _file_mapping(selected: Any, *names: str) -> dict[str, Any] | None:
    path = _path(selected, *names)
    if path is None:
        return None
    value = load_json(path)
    require(isinstance(value, Mapping), f"{names[0]} must contain a mapping")
    return dict(value)


def _options(selected: Any) -> dict[str, Any]:
    options = getattr(selected, "options", {})
    require(isinstance(options, Mapping), "pve-template options must be a mapping")
    return dict(options)


def _write_json(path: Path, value: Mapping[str, Any], *, secure: bool = False) -> None:
    write_text(path, json.dumps(value, sort_keys=True, indent=2) + "\n", secure=secure)


def _helper_command(selected: Any, operation: str) -> list[str]:
    options = _options(selected)
    configured = options.get("helper_command") or os.environ.get("IAAS_PVE_TEMPLATE_HELPER")
    constructed = configured is None
    if configured is None:
        documents = getattr(selected, "documents", {})
        recipe = documents.get("recipe", documents.get("template", documents.get("build", {})))
        target = recipe.get("target", {}) if isinstance(recipe, Mapping) else options.get("target", {})
        require(isinstance(target, Mapping), "pve-template helper target is required")
        host = target.get("host")
        user = target.get("ssh_user", "pve-ops")
        require(isinstance(host, str) and host and isinstance(user, str) and user and
                not host.startswith("-") and not user.startswith("-") and
                all(char.isprintable() and not char.isspace() for char in host) and
                all(char.isprintable() and not char.isspace() for char in user),
                "pve-template helper SSH target is invalid")
        known_hosts = getattr(selected, "files", {}).get("known_hosts")
        ssh_key = getattr(selected, "files", {}).get("ssh_key")
        require(known_hosts is not None and ssh_key is not None,
                "pve-template online operation requires explicit SSH key and known_hosts")
        port = target.get("ssh_port", 22)
        require(type(port) is int and 1 <= port <= 65535, "pve-template SSH port is invalid")
        configured = ["ssh", "-T", "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
                      "-o", "IdentityAgent=none", "-o", "StrictHostKeyChecking=yes",
                      "-o", f"UserKnownHostsFile={known_hosts}", "-p", str(port), "-i", str(ssh_key),
                      f"{user}@{host}", "sudo", "-n", "/usr/local/sbin/iaas-pve-template"]
    if isinstance(configured, str):
        command = [configured]
    else:
        require(isinstance(configured, list) and all(isinstance(item, str) for item in configured),
                "pve-template helper_command must be a command list")
        command = list(configured)
    # No caller-supplied command flags are accepted.  The operation travels in
    # the validated JSON document on stdin.
    if not constructed:
        require(all(item and not item.startswith("-") for item in command),
                "pve-template helper command may not contain flags")
    return command


def _invoke_helper(selected: Any, execution: Any, request: Mapping[str, Any], phase: str) -> dict[str, Any]:
    payload = json.dumps(request, sort_keys=True) + "\n"
    command = _helper_command(selected, str(request["operation"]))
    work = execution.outputs.path("work")
    input_path = work / f"{phase}.request.json"
    output_path = work / f"{phase}.response.json"
    stderr_path = work / f"{phase}.stderr.txt"
    write_text(input_path, payload, secure=True)
    try:
        result = subprocess.run(command, input=payload, text=True, capture_output=True,
                                cwd=work, env=execution.environ, check=False,
                                timeout=HELPER_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        write_text(output_path, str(exc.stdout or ""), secure=True)
        write_text(stderr_path, str(exc.stderr or ""), secure=True)
        raise OperationFailed(f"{phase} timed out; inspect protected task recovery material") from None
    except OSError as exc:
        write_text(stderr_path, str(exc), secure=True)
        raise OperationFailed(f"{phase} could not start; inspect protected task recovery material") from exc
    write_text(output_path, result.stdout, secure=True)
    write_text(stderr_path, result.stderr or "", secure=True)
    if result.returncode != 0:
        raise OperationFailed(f"{phase} failed; inspect protected task recovery material")
    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise OperationFailed(f"{phase} returned an invalid helper response") from exc
    require(isinstance(response, dict), "helper response must be a mapping")
    return response


def _poll_remote(selected: Any, execution: Any, execution_id: str, initial: Mapping[str, Any]) -> dict[str, Any]:
    """Observe a submitted worker without replaying it after a disconnect."""
    state = initial.get("execution", {}).get("state") if isinstance(initial.get("execution"), Mapping) else None
    latest = dict(initial)
    deadline = time.monotonic() + float(_options(selected).get("poll_timeout", 60))
    while state in {"admitted", "running"}:
        if time.monotonic() >= deadline:
            return {"status": "unknown", "execution": latest.get("execution", latest),
                    "reason": "bounded observation window elapsed"}
        time.sleep(0.2)
        request = validate_request({"protocol_version": HELPER_PROTOCOL_VERSION,
                                    "operation": "query", "execution_id": execution_id})
        try:
            latest = _invoke_helper(selected, execution, request, "query")
        except OperationFailed:
            return {"status": "unknown", "execution": latest.get("execution", latest),
                    "reason": "controller lost contact; remote state is unconfirmed"}
        observed = latest.get("execution")
        state = observed.get("state") if isinstance(observed, Mapping) else None
    if state == "succeeded":
        return dict(latest)
    if state in {"failed", "unknown"}:
        return dict(latest)
    return {"status": "unknown", "execution": latest.get("execution", latest),
            "reason": "remote state is unrecognized"}


def _runtime(image_digest: str) -> dict[str, Any]:
    require(isinstance(image_digest, str) and image_digest, "pve-template requires a resolved runtime image digest")
    return {"image_digest": image_digest}


def _record_bundle(value: Any, *, target: Mapping[str, Any] | None = None,
                   complete: bool = False) -> dict[str, Any]:
    """Normalize helper observations to the records consumed by VM planning."""
    source = value if isinstance(value, Mapping) else {}
    if isinstance(source.get("execution"), Mapping) and isinstance(source["execution"].get("template_record"), Mapping):
        source = {**dict(source), "template_record": source["execution"]["template_record"]}
    if isinstance(source.get("template_record"), Mapping):
        source = source["template_record"]
    records = source.get("records") if isinstance(source, Mapping) else None
    if not isinstance(records, list):
        candidate = source.get("record") if isinstance(source, Mapping) else None
        if isinstance(candidate, Mapping):
            records = [candidate]
        else:
            template = source.get("template") if isinstance(source, Mapping) else None
            if isinstance(template, Mapping):
                records = [{"schema_version": 1,
                            "record_id": f"template-observed-{template.get('vmid', 'unknown')}",
                            "target": dict(target or template.get("target", {})),
                            "object": {key: template.get(key) for key in
                                       ("node", "vmid", "smbios_uuid", "disks")},
                            "configuration": template.get("configuration", {})}]
            else:
                records = []
    normalized: list[dict[str, Any]] = []
    for item in records:
        row = dict(item) if isinstance(item, Mapping) else {}
        if not row.get("record_id") and isinstance(source.get("record_id"), str):
            row["record_id"] = source["record_id"]
        if target and not isinstance(row.get("target"), Mapping):
            row["target"] = dict(target)
        elif target and isinstance(row.get("target"), Mapping):
            row["target"] = {**dict(target), **dict(row["target"])}
        normalized.append(validate_template_record(row, complete=complete))
    if not records and isinstance(source.get("object"), Mapping):
        row = {"schema_version": 1, "record_id": source.get("record_id", "template-result"),
               "target": dict(target or source.get("target", {})), "object": source["object"],
               "configuration": source.get("configuration", {})}
        normalized.append(validate_template_record(row, complete=complete))
    return {"schema_version": 1, "records": normalized}


def _safe_response_summary(response: Mapping[str, Any]) -> dict[str, Any]:
    execution = response.get("execution")
    summary: dict[str, Any] = {"status": response.get("status", "unknown")}
    if isinstance(execution, Mapping):
        summary["execution_state"] = execution.get("state")
        summary["execution_id"] = execution.get("execution_id")
    if isinstance(response.get("template_record"), Mapping):
        records = response["template_record"].get("records")
        summary["records"] = len(records) if isinstance(records, list) else 0
    return summary


def _require_observation_known(response: Mapping[str, Any]) -> None:
    execution = response.get("execution")
    if isinstance(execution, Mapping):
        require(execution.get("state") != "unknown" and
                execution.get("remote_activity") != "unknown",
                "template query state is unknown; inspect protected task recovery material")
    require(response.get("status") not in {"unknown", "timeout", "disconnected"},
            "template query state is unknown; inspect protected task recovery material")


def run(selected: Any, operation: str, scope: str, execution: Any,
        image_digest: str, execution_id: str = "") -> None:
    """Run an independent pve-template operation through the shared launcher."""
    require(operation in {"check", "read", "plan", "apply", "verify"},
            "unsupported pve-template operation")
    options = _options(selected)
    allowed = {
        "check": {"helper_command"}, "read": {"helper_command", "template", "execution_id"},
        "plan": {"helper_command", "action", "admission", "recovery_of", "cleanup", "execution_id"},
        "apply": {"helper_command", "preview_digest", "admission", "action", "recovery_of", "poll_timeout", "template_admission"},
        "verify": {"helper_command", "receipt", "execution_id", "template"},
    }[operation]
    require(not set(options) - allowed, "unknown pve-template operation option")
    if "poll_timeout" in options:
        require(type(options["poll_timeout"]) in {int, float} and 0 < options["poll_timeout"] <= 300,
                "pve-template poll_timeout must be bounded")
    if scope:
        require(isinstance(scope, str) and scope not in {"all", "localhost"},
                "pve-template scope must select one explicit node")

    if operation == "check":
        recipe = validate_recipe(_document(selected))
        execution.finish({"component": "pve-template", "operation": operation,
                          "schema_version": 1, "recipe_digest": canonical_digest(recipe),
                          "network": False, "state": False})
        return

    recipe_for_scope = validate_recipe(_document(selected))
    require(scope == recipe_for_scope["target"]["node"],
            "pve-template online operation scope must select the recipe target node")

    if operation == "plan":
        action = options.get("action", "build")
        require(action in {"build", "cleanup"}, "pve-template plan action must be build or cleanup")
        if action == "build":
            recipe = validate_recipe(_document(selected))
            preview = build_preview(recipe, runtime=_runtime(image_digest),
                                    helper={"protocol_version": HELPER_PROTOCOL_VERSION})
            capabilities = _invoke_helper(selected, execution,
                                          {"protocol_version": HELPER_PROTOCOL_VERSION,
                                           "operation": "capabilities"}, "capabilities")
            require(capabilities.get("protocol_version") == HELPER_PROTOCOL_VERSION,
                    "template helper protocol is incompatible")
            prerequisite = _invoke_helper(selected, execution,
                                          {"protocol_version": HELPER_PROTOCOL_VERSION,
                                           "operation": "check", "preview": preview}, "prerequisites")
            _write_json(execution.outputs.path("diagnostics") / "helper-capabilities.json", capabilities, secure=True)
            _write_json(execution.outputs.path("diagnostics") / "helper-prerequisites.json", prerequisite, secure=True)
        else:
            cleanup = options.get("cleanup")
            require(isinstance(cleanup, Mapping), "cleanup plan requires cleanup input")
            cleanup_execution_id = execution_id or options.get("execution_id", "cleanup-preview")
            cleanup_request = {**dict(cleanup), "runtime": _runtime(image_digest),
                               "helper": {"protocol_version": HELPER_PROTOCOL_VERSION}}
            request = validate_request({"protocol_version": HELPER_PROTOCOL_VERSION,
                                        "operation": "cleanup_preview", "execution_id": cleanup_execution_id,
                                        "cleanup": cleanup_request})
            response = _invoke_helper(selected, execution, request, "cleanup-preview")
            preview = dict(response.get("preview", response))
            for key in ("state_owner", "state_ref_absent", "retirement_authorized", "dependencies_resolved"):
                if key in cleanup:
                    preview[key] = cleanup[key]
            # Cleanup previews are bound to the same runtime/helper identity as
            # build previews.  Older helper output is rejected rather than
            # silently upgraded at apply time.
            preview = validate_cleanup_preview(preview)
            require(preview["runtime"] == cleanup_request["runtime"] and
                    preview["helper"] == cleanup_request["helper"],
                    "cleanup preview runtime/helper does not match selected runtime")
        _write_json(execution.outputs.path("plan") / "template-preview.json", preview, secure=True)
        execution.finish({"component": "pve-template", "operation": operation,
                          "action": action, "preview_digest": preview.get("preview_digest"),
                          "network": action == "cleanup"})
        return

    if operation == "read":
        if not execution_id and not isinstance(options.get("execution_id"), str):
            historical = options.get("template") or _file_mapping(selected, "execution_result", "result")
            require(isinstance(historical, Mapping), "pve-template read requires execution_id or template observation")
            if isinstance(historical.get("template_record"), Mapping):
                records = historical["template_record"].get("records", [])
                identity = records[0].get("object", {}) if records and isinstance(records[0], Mapping) else {}
            elif isinstance(historical.get("records"), list) and historical["records"]:
                identity = historical["records"][0].get("object", {})
            else:
                identity = historical.get("template", historical.get("object", historical))
            require(isinstance(identity, Mapping), "template observation identity is missing")
            request = validate_request({"protocol_version": HELPER_PROTOCOL_VERSION,
                                        "operation": "observe", "template": dict(identity)})
            observed = _invoke_helper(selected, execution, request, "observe")
            target = historical.get("target") if isinstance(historical.get("target"), Mapping) else None
            if target is None and isinstance(identity.get("target"), Mapping):
                target = identity["target"]
            if target is None:
                try:
                    candidate = _document(selected).get("target")
                except Exception:
                    candidate = None
                target = candidate if isinstance(candidate, Mapping) else None
            records = _record_bundle(observed, target=target, complete=False)
            observation = {"kind": "historical_observation", "status": observed.get("status", "unknown"),
                           "template": observed.get("template", {}), "records": records,
                           "build_history": observed.get("build_history", "unknown"),
                           "cleaning_history": "unknown", "publication": "caller_owned"}
            _write_json(execution.outputs.path("diagnostics") / "observation.json", observation, secure=True)
            execution.finish({"component": "pve-template", "operation": operation,
                              "status": observation["status"], "records": len(records["records"]),
                              "cleaning_history": "unknown"})
            return
        selected_id = execution_id or options["execution_id"]
        request = validate_request({"protocol_version": HELPER_PROTOCOL_VERSION,
                                    "operation": "query", "execution_id": selected_id})
        response = _invoke_helper(selected, execution, request, "query")
        _write_json(execution.outputs.path("diagnostics") / "observation.json", response, secure=True)
        _require_observation_known(response)
        execution.finish({"component": "pve-template", "operation": operation,
                          "execution_id": selected_id, **_safe_response_summary(response)})
        return

    if operation == "verify":
        source = _path(selected, "receipt", "template_receipt", "execution_result", "result")
        require(source is not None or isinstance(options.get("receipt"), Mapping),
                "pve-template verify requires a receipt")
        value = dict(options["receipt"]) if isinstance(options.get("receipt"), Mapping) else load_json(source)  # type: ignore[arg-type]
        require(isinstance(value, Mapping), "template receipt must be a mapping")
        require(value.get("schema_version") == 1 and value.get("kind") == "pve-template-receipt",
                "unsupported template receipt")
        verified = "unknown"
        current: Mapping[str, Any] = {}
        current_record: Mapping[str, Any] = {}
        receipt_object = value.get("object")
        if not isinstance(receipt_object, Mapping) and isinstance(value.get("template_record"), Mapping):
            receipt_object = value["template_record"].get("object")
        try:
            execution_id_value = value.get("execution_id")
            require(isinstance(execution_id_value, str), "template receipt execution_id is missing")
            recipe = validate_recipe(_document(selected))
            require(scope == recipe["target"]["node"],
                    "pve-template verify scope must select the recipe target node")
            receipt_target = value.get("target")
            require(isinstance(receipt_target, Mapping) and
                    dict(receipt_target) == recipe["target"],
                    "template receipt target does not match current recipe SSH target")
            observed = _invoke_helper(selected, execution,
                                      {"protocol_version": HELPER_PROTOCOL_VERSION,
                                       "operation": "observe",
                                       "template": {"node": receipt_object.get("node") if isinstance(receipt_object, Mapping) else None,
                                                     "vmid": receipt_object.get("vmid") if isinstance(receipt_object, Mapping) else None}},
                                      "verify-observe")
            _require_observation_known(observed)
            records = _record_bundle(observed, target=recipe["target"], complete=False)["records"]
            current_record = records[0] if records else {}
            current = current_record.get("object", {})
            receipt_record = value if isinstance(value.get("configuration"), Mapping) else value.get("template_record", {})
            expected_configuration = receipt_record.get("configuration", {}) if isinstance(receipt_record, Mapping) else {}
            current_configuration = current_record.get("configuration", {}) if isinstance(current_record, Mapping) else {}
            identity_fields = ("node", "vmid", "smbios_uuid", "disks")
            complete = (isinstance(receipt_object, Mapping) and all(receipt_object.get(field) not in (None, {}, "")
                                                                     for field in identity_fields)
                        and all(current.get(field) not in (None, {}, "") for field in identity_fields))
            if complete and all(current.get(field) == receipt_object.get(field) for field in identity_fields) \
                    and isinstance(expected_configuration, Mapping) and bool(expected_configuration) \
                    and all(current_configuration.get(key) == value for key, value in expected_configuration.items()):
                verified = "passed"
            else:
                verified = "failed"
        except ValidationError:
            verified = "unknown"
        verification = {"receipt": value, "current": current, "status": verified,
                        "configuration": current_record.get("configuration", {}) if isinstance(current_record, Mapping) else {},
                        "cleaning_history": value.get("cleaning_history", "unknown"),
                        "scope": "native-template-identity-and-configuration"}
        _write_json(execution.outputs.path("diagnostics") / "verification.json", verification, secure=True)
        require(verified == "passed", "template configuration verification did not pass")
        execution.finish({"component": "pve-template", "operation": operation,
                          "execution_id": value.get("execution_id"),
                          "status": verified,
                          "clone_verification": value.get("clone_verification", "not_performed"),
                          "cleaning_history": value.get("cleaning_history", "unknown")})
        return

    # Apply consumes an exact, caller-selected preview.  It does not re-plan
    # or infer admission from a fresh execution ID.
    source = _path(selected, "preview", "template_preview")
    require(source is not None, "pve-template apply requires a selected preview")
    raw_preview = load_json(source)
    require(isinstance(raw_preview, Mapping), "pve-template preview must be a mapping")
    is_cleanup = raw_preview.get("kind") == "pve-template-cleanup-preview"
    preview = validate_cleanup_preview(raw_preview) if is_cleanup else validate_preview(raw_preview)
    require(recipe_for_scope["target"] ==
            (preview["target"] if is_cleanup else preview["fixed_input"]["target"]),
            "pve-template apply recipe target does not match selected preview")
    require(execution_id and isinstance(execution_id, str), "pve-template apply requires execution_id")
    require(options.get("preview_digest") == preview["preview_digest"],
            "pve-template apply preview digest is missing or stale")
    require(preview["runtime"]["image_digest"] == image_digest,
            "pve-template apply runtime image does not match selected preview")
    require(preview["helper"]["protocol_version"] == HELPER_PROTOCOL_VERSION,
            "pve-template apply helper protocol does not match selected preview")
    if is_cleanup:
        require(options.get("action") == "cleanup", "cleanup apply requires action=cleanup")
        admission = options.get("admission") or _file_mapping(selected, "execution_admission", "template_admission")
        require(isinstance(admission, Mapping), "cleanup apply requires current cleanup admission")
        request = validate_request({"protocol_version": HELPER_PROTOCOL_VERSION, "operation": "cleanup",
                                    "execution_id": execution_id, "recovery_of": preview["original_execution"],
                                    "cleanup": {**preview, "management_status": "stopped"},
                                    "admission": dict(admission)})
        response = _invoke_helper(selected, execution, request, "cleanup")
        require(response.get("status") == "succeeded", "template cleanup did not complete")
        cleanup_receipt = response.get("receipt") if isinstance(response.get("receipt"), Mapping) else {
            "schema_version": 1, "kind": "pve-template-cleanup-receipt",
            "execution_id": execution_id, "recovery_of": preview["original_execution"],
            "status": response.get("status"), "effects": response.get("effects", "unknown"),
            "preview_digest": preview["preview_digest"],
        }
        _write_json(execution.outputs.path("diagnostics") / "receipt.json", cleanup_receipt, secure=True)
        execution.finish({"component": "pve-template", "operation": operation, "action": "cleanup",
                          "execution_id": execution_id, "recovery_of": preview["original_execution"],
                          "effects": "known", "status": "succeeded"})
        return
    admission = options.get("admission") or _file_mapping(selected, "execution_admission", "template_admission")
    require(isinstance(admission, Mapping), "pve-template apply requires execution admission")
    template_admission = options.get("template_admission") or _file_mapping(selected, "template_admission")
    request = validate_request({"protocol_version": HELPER_PROTOCOL_VERSION, "operation": "submit",
                                "execution_id": execution_id, "preview": preview,
                                "admission": admission,
                                **({"template_admission": template_admission} if template_admission else {})})
    response = _invoke_helper(selected, execution, request, "submit")
    response = _poll_remote(selected, execution, execution_id, response)
    receipt_value = response.get("receipt") if isinstance(response.get("receipt"), Mapping) else response
    execution_state = response.get("execution", {}).get("state") if isinstance(response.get("execution"), Mapping) else None
    if response.get("status") in {"unknown", "failed"} or execution_state not in {None, "succeeded"}:
        raise OperationFailed("remote template execution did not reach a confirmed success")
    records = _record_bundle(response, target=preview["fixed_input"]["target"], complete=True)
    require(records["records"], "remote template execution returned no complete template records")
    _write_json(execution.outputs.path("generated") / "template-records.json", records, secure=True)
    bare_receipt = {key: value for key, value in receipt_value.items()
                    if key not in {"execution", "template_record", "receipt"}}
    bare_receipt.update(schema_version=1, kind="pve-template-receipt", execution_id=execution_id,
                        preview_digest=preview["preview_digest"], status="succeeded",
                        target=preview["fixed_input"]["target"],
                        record_id=records["records"][0]["record_id"],
                        object=records["records"][0]["object"],
                        configuration=records["records"][0]["configuration"],
                        cleaning_history="unknown")
    _write_json(execution.outputs.path("diagnostics") / "receipt.json", bare_receipt, secure=True)
    execution.finish({"component": "pve-template", "operation": operation,
                      "execution_id": execution_id, "preview_digest": preview["preview_digest"],
                      "records": len(records["records"]), "effects": "known", "status": "succeeded"})

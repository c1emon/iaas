"""Saved native plans and companion inputs; SSH always follows static admission."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Any

from iaas_automation.common.errors import require
from iaas_automation.common.io import write_text
from iaas_automation.pve_inventory.cloud_init_helpers.artifacts import load_rendered_artifacts, manifest_path
from iaas_automation.runtime_config.compile import compile_documents
from iaas_automation.runtime_config.loader import SelectedConfig
from iaas_automation.runtime_config.selection import runtime_platform
from .dependencies import restore_dependencies
from .credentials import protected_file
from .execution import Execution
from .root import materialize_root, relative_path
from .state import S3Backend
from .pve_contracts import (validate_execution_admission, validate_plan_metadata,
                            validate_verification_requirements, validate_result)
from .pve_results import machine_review, expectations, verify_configuration, api_client, template_identity


def sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def target_selection(selected: SelectedConfig, scope: str, image_digest: str) -> dict[str, Any]:
    require(re.fullmatch(r"[^@]+@sha256:[0-9a-f]{64}", image_digest), "saved plans require a resolved image digest")
    root = selected.options.get("root", {})
    require(isinstance(root, dict) and scope and scope == root.get("id"),
            "PVE scope must explicitly select the complete declared root id")
    target = selected.options.get("pve", {})
    require(isinstance(target, dict)
            and {"storage_id", "ssh_host", "ssh_user", "api_endpoint", "insecure"} <= set(target)
            and set(target) <= {"storage_id", "ssh_host", "ssh_user", "api_endpoint", "insecure", "ssh_port"},
            "PVE plan requires fixed API, TLS and SSH target")
    require(all(isinstance(target[name], str) and target[name]
                for name in ("storage_id", "ssh_host", "ssh_user", "api_endpoint")), "PVE target fields must be strings")
    require(type(target["insecure"]) is bool, "PVE TLS mode must be explicit")
    require(re.fullmatch(r"[A-Za-z0-9_.:\[\]-]+", target["ssh_host"])
            and re.fullmatch(r"[a-z_][a-z0-9_-]*", target["ssh_user"]), "invalid PVE SSH target")
    return {"environment": selected.environment, "scenario": selected.scenario, "scope": scope,
            "root_id": root["id"], "image_digest": image_digest, "runtime_platform": runtime_platform(), "target": target}


def _json(path: Path) -> dict:
    protected_file(path)
    document = json.loads(path.read_text())
    require(isinstance(document, dict), "PVE material must be a JSON object")
    return document


def _write(path: Path, document: dict) -> None:
    write_text(path, json.dumps(document, indent=2) + "\n", secure=True)


def _verification(selected: SelectedConfig) -> dict:
    return validate_verification_requirements(selected.options.get("verification_requirements", {
        "requirements": [{"category": "configuration", "scope": "changed_objects", "required": True,
                          "responsibility": "iaas"},
                         {"category": "guest", "scope": "changed_objects", "required": False,
                          "responsibility": "caller"}]}))


def _templates(selected: SelectedConfig, dependencies: list[dict], target: dict, api: Any) -> list[dict]:
    records = _json(selected.files["template_records"]).get("records", []) if dependencies else []
    bound = []
    for dependency in dependencies:
        matches = [r for r in records if r.get("object", {}).get("node") == dependency["node"]
                   and r.get("object", {}).get("vmid") == dependency["vmid"]]
        require(len(matches) == 1, "clone dependency requires one template record")
        record = matches[0]
        record_target = record.get("target", {})
        endpoint = record_target.get("api_endpoint", record_target.get("endpoint"))
        require(record.get("schema_version") == 1 and record.get("record_id")
                and isinstance(endpoint, str) and endpoint.rstrip("/") == target["api_endpoint"].rstrip("/")
                and record_target.get("insecure") == target["insecure"], "template record target or version mismatch")
        config = api.vm_config(dependency["node"], dependency["vmid"])
        require(config.get("template") in (True, 1, "1"), "clone source is not a template")
        identity = template_identity(config)
        require(all(record["object"].get(key) == value for key, value in identity.items()),
                "template native identity changed")
        facts = record.get("configuration")
        require(isinstance(facts, dict) and bool(facts) and _facts_match(facts, config),
                "template configuration changed or missing")
        bound.append(record)
    return bound


def _facts_match(facts: dict, config: dict) -> bool:
    return all(k in config and str(config[k]) == str(v) for k, v in facts.items())


def _admit_templates(metadata: dict, selected: SelectedConfig, execution_id: str, api: Any) -> None:
    records = metadata["template_records"]
    if not records:
        return
    from .pve_contracts import validate_template_admission
    admissions = _json(selected.files["template_admission"]).get("admissions", [])
    for record in records:
        matches = [r for r in admissions if r.get("record_id") == record["record_id"]]
        require(len(matches) == 1, "current template admission missing or ambiguous")
        admission = validate_template_admission(matches[0])
        require(admission["execution_id"] == execution_id and admission["plan_digest"] == metadata["plan_digest"]
                and admission.get("target") == metadata["target"] and admission["object"] == record["object"],
                "template admission association mismatch")
        if admission["status"] == "pending_validation":
            require(admission["purpose"] == "verification" and admission.get("approved") is True
                    and admission.get("scope") == metadata["root_id"]
                    and metadata.get("template_use", {}).get("purpose") == "verification"
                    and admission.get("vmids") == metadata["template_use"]["vmids"],
                    "pending template requires bounded validation authorization")
        else:
            require(admission["status"] == "available", "template is not currently available")
        obj = record["object"]
        config = api.vm_config(obj["node"], obj["vmid"])
        require(config.get("template") in (True, 1, "1")
                and all(obj.get(k) == v for k, v in template_identity(config).items())
                and _facts_match(record["configuration"], config),
                "template object was replaced or changed")


def prepare_plan(selected: SelectedConfig, execution: Execution, backend: S3Backend,
                 scope: str, image_digest: str, tofu: str = "tofu") -> Path:
    from .pve_state import observe_state, admit_state
    from .pve_provider import (validate_root, validate_plan_provider, prepare_provider_environment,
                              verify_ssh_trust, verify_helper_trust)
    metadata = target_selection(selected, scope, image_digest)
    generated = compile_documents(selected)
    bundle = execution.outputs.path("plan")
    root = materialize_root(selected.options["root"], selected.files, bundle / "workspace")
    provider = validate_root(root, metadata["target"])
    prepare_provider_environment(provider, selected.files, execution.environ)
    before = observe_state(backend, execution.environ)
    admission = _json(selected.files["state_admission"])
    require(admission.get("root_id") == scope, "state admission root mismatch")
    admit_state(backend, admission, before)
    api = api_client(metadata["target"], execution.environ)
    _check_declared_conflicts(json.loads(generated["pve.tfvars.json"])["vms"], before.raw, api)
    vms = json.loads(generated["pve.tfvars.json"])["vms"]
    purpose = selected.options.get("template_purpose", "execution")
    require(purpose in {"execution", "verification"}, "unsupported template purpose")
    if purpose == "verification":
        require(bool(vms) and all(vm["lifecycle_class"] == "ephemeral_lab" for vm in vms),
                "template verification requires an explicit temporary VM root")
    declared_nodes = {node for vm in vms for node in (vm["node"], vm["template"]["node"])}
    verify_ssh_trust(provider, selected.files, execution.environ, state=before.raw, declared_nodes=declared_nodes)
    tfvars = bundle / "inputs.tfvars.json"
    write_text(tfvars, generated["pve.tfvars.json"], secure=True)
    snippets = bundle / "snippets"
    storage = metadata["target"]["storage_id"]
    execution.run("render-snippets", [sys.executable, "-m", "iaas_automation.pve_inventory.cloud_init", "render",
                                      "--tfvars", str(tfvars), "--output-dir", str(snippets), "--storage-id", storage], root)
    if load_rendered_artifacts(snippets, storage, tfvars, allow_empty=True):
        verify_helper_trust(metadata["target"], selected.files)
    mirror = None
    if "dependencies" in selected.files:
        shutil.copyfile(selected.files["dependencies"], bundle / "dependencies.tar.gz")
        (bundle / "dependencies.tar.gz").chmod(0o600)
        mirror = restore_dependencies(bundle / "dependencies.tar.gz", root, execution.outputs.path("work") / "dependencies")
    execution.environ.update(TF_WORKSPACE=backend.workspace, TF_IN_AUTOMATION="1", TF_INPUT="0")
    result = backend.initialize(root, execution.environ, execution.outputs.path("recovery"), tofu, plugin_dir=mirror)
    execution.record("backend-init", result, root)
    initialized = observe_state(backend, execution.environ)
    _state_transition(before.to_dict(), initialized.to_dict(), allow_initialization=True)
    admit_state(backend, admission, initialized)
    plan = bundle / "plan.tfplan"
    destroy = selected.options.get("destroy", False)
    require(type(destroy) is bool, "destroy must be an explicit boolean")
    execution.run("plan", [tofu, "plan", "-input=false", "-lock-timeout=30s", *(["-destroy"] if destroy else []),
                           f"-var-file={tfvars}", f"-out={plan}"], root)
    require(plan.is_file(), "successful tool exit did not produce a native plan")
    plan.chmod(0o600)
    review = execution.run("review", [tofu, "show", "-no-color", str(plan)], root)
    shutil.copyfile(review.capture, bundle / "review.txt")
    (bundle / "review.txt").chmod(0o600)
    native_result = execution.run("review-json", [tofu, "show", "-json", str(plan)], root)
    native = _json(native_result.capture)
    validate_plan_provider(native, provider, metadata["target"])
    verify_ssh_trust(provider, selected.files, execution.environ, state=before.raw, plan=native)
    safe_review, changes, dependencies = machine_review(native)
    _write(bundle / "native-plan.json", native)
    _write(bundle / "review.json", safe_review)
    records = _templates(selected, dependencies, metadata["target"], api)
    _check_resource_conflicts(changes, before.raw, api)
    planned_state = observe_state(backend, execution.environ)
    _state_transition(initialized.to_dict(), planned_state.to_dict(), allow_initialization=True)
    admit_state(backend, admission, planned_state)
    manifest_file = manifest_path(snippets)
    manifest = json.loads(manifest_file.read_text())
    manifest["plan_sha256"] = sha256(plan)
    write_text(manifest_file, json.dumps(manifest, indent=2) + "\n", secure=True)
    metadata.update(schema_version=2, backend=backend.identity(), workspace=backend.workspace,
                    runtime=image_digest, plan_digest=sha256(plan),
                    state_admission=admission, state_before=before.to_dict(),
                    state_initialized=planned_state.to_dict(), provider=provider,
                    template_use={"purpose": purpose, "vmids": sorted(vm["vmid"] for vm in vms)},
                    verification_requirements=_verification(selected), changes=changes, template_records=records,
                    root_directory=str(root.relative_to(bundle)),
                    companion_files=sorted(
                        ["workspace/" + relative_path(name).as_posix() for name in selected.options["root"]["files"]]
                        + (["dependencies.tar.gz"] if "dependencies" in selected.files else [])),
                    provider_lock_sha256=sha256(root / ".terraform.lock.hcl"),
                    input_origins=sorted(map(str, selected.reader.logical_sources)))
    validate_plan_metadata(metadata)
    _write(bundle / "summary.json", metadata)
    # Initialization state and provider caches are not part of the transferable
    # root. The separate dependency archive supplies locked tools for later init.
    if (root / ".terraform").exists():
        shutil.rmtree(root / ".terraform")
    (root / "zz_iaas_backend_override.tf.json").unlink()
    execution.finish({"operation": "plan", "environment": selected.environment,
                      "plan": str(plan), "authorization": "application requires explicit caller selection"})
    return plan


def admit_plan(plan: Path, bundle: Path, expected: dict[str, Any], backend: S3Backend | None) -> tuple[dict[str, Any], Path]:
    protected_file(plan)
    metadata = json.loads((bundle / "summary.json").read_text())
    require(metadata.get("schema_version") == 2, "unsupported saved-plan metadata; generate a new v2 plan")
    validate_plan_metadata(metadata)
    require(all(metadata.get(key) == value for key, value in expected.items()), "saved plan target or runtime mismatch")
    if backend is not None:
        require(metadata.get("backend") == backend.identity(), "saved plan backend/workspace mismatch")
    files = metadata.get("companion_files")
    require(isinstance(files, list) and bool(files), "saved companion file list is missing; prepare the plan again")
    for name in files:
        path = bundle.joinpath(*relative_path(name).parts)
        require(path.resolve().is_relative_to(bundle.resolve()) and path.is_file(),
                "saved companion file is missing or outside its bundle")
    root = bundle.joinpath(*relative_path(metadata["root_directory"]).parts)
    require(root.resolve().is_relative_to(bundle.resolve()), "saved root escapes companion directory")
    require(sha256(root / ".terraform.lock.hcl") == metadata.get("provider_lock_sha256"), "saved provider lock mismatch")
    manifest = json.loads(manifest_path(bundle / "snippets").read_text())
    require(isinstance(manifest.get("plan_sha256"), str) and sha256(plan) == manifest["plan_sha256"],
            "native plan does not match companion manifest")
    require(metadata["plan_digest"] == sha256(plan), "native plan does not match metadata")
    load_rendered_artifacts(bundle / "snippets", metadata["target"]["storage_id"], bundle / "inputs.tfvars.json", allow_empty=True)
    return metadata, root


def _state_transition(prior: dict, current: dict, *, allow_initialization: bool = False) -> None:
    require(current.get("status") in {"absent", "present"}, "state observation failed")
    if prior.get("status") == "present":
        require(current.get("status") == "present" and current.get("lineage") == prior.get("lineage"),
                "previously observed state disappeared or changed lineage")
    elif prior.get("status") == "absent" and current.get("status") == "present":
        require(allow_initialization and current.get("empty") is True,
                "unassociated state appeared after planning")


def _check_resource_conflicts(changes: list[dict], state: dict | None, api: Any) -> None:
    from .pve_results import state_instances, VM_TYPE
    managed = {(i.get("attributes", {}).get("node_name"), i.get("attributes", {}).get("vm_id"))
               for rows in state_instances(state or {}).values() for i in rows}
    for item in changes:
        if item["type"] != VM_TYPE:
            continue
        after = item["change"].get("after") or {}
        if "create" not in item["change"]["actions"]:
            continue
        node, vmid = after.get("node_name"), after.get("vm_id")
        require(isinstance(node, str) and type(vmid) is int, "plan requires known VM placement")
        if (node, vmid) in managed:
            continue
        from iaas_automation.pve_inventory.pve_api import PveApiNotConfiguredError
        try:
            api.vm_config(node, vmid)
        except PveApiNotConfiguredError:
            continue
        require(False, "VMID is occupied outside selected state")


def _check_declared_conflicts(vms: list[dict], state: dict | None, api: Any) -> None:
    from .pve_results import state_instances
    managed = {i.get("attributes", {}).get("vm_id")
               for rows in state_instances(state or {}).values() for i in rows}
    inventory = api.cluster_vm_resources()
    require(isinstance(inventory, list), "PVE resource observation is incomplete")
    occupied = {int(row["vmid"]) for row in inventory if row.get("vmid") is not None}
    require(not ({vm["vmid"] for vm in vms} & occupied) - managed,
            "declared VMID is occupied outside selected state")


def apply_saved_plan(plan: Path, bundle: Path, selected: SelectedConfig, execution: Execution,
                     backend: S3Backend, scope: str, image_digest: str, tofu: str = "tofu",
                     *, execution_id: str = "") -> None:
    from .pve_state import observe_state, admit_state
    from .pve_provider import validate_root, prepare_provider_environment, verify_ssh_trust, verify_helper_trust
    expected = target_selection(selected, scope, image_digest)
    # Admission before copying, init, upload or any other infrastructure write.
    metadata, _ = admit_plan(plan, bundle, expected, backend)
    admission = _json(selected.files["execution_admission"])
    validate_execution_admission(admission, digest=metadata["plan_digest"], target=metadata["target"], execution_id=execution_id)
    require("verification_requirements" not in selected.options
            or _verification(selected) == metadata["verification_requirements"], "verification requirements cannot change after plan")
    state_admission = _json(selected.files["state_admission"])
    require(state_admission.get("root_id") == scope, "state admission root mismatch")
    before = observe_state(backend, execution.environ)
    _state_transition(metadata["state_initialized"], before.to_dict())
    admit_state(backend, state_admission, before)
    require(not any(path.is_symlink() for path in bundle.rglob("*")), "saved companion directory contains a symlink")
    retained = execution.outputs.path("plan") / "selected"
    shutil.copytree(bundle, retained)
    shutil.copyfile(plan, retained / "plan.tfplan")
    for path in retained.rglob("*"):
        path.chmod(0o700 if path.is_dir() else 0o600 | (path.stat().st_mode & 0o100))
    _, root = admit_plan(retained / "plan.tfplan", retained, expected, backend)
    provider = validate_root(root, metadata["target"])
    require(provider == metadata["provider"], "saved provider configuration changed")
    prepare_provider_environment(provider, selected.files, execution.environ)
    verify_ssh_trust(provider, selected.files, execution.environ, state=before.raw, plan=_json(retained / "native-plan.json"))
    target = metadata["target"]
    api = api_client(target, execution.environ)
    _admit_templates(metadata, selected, execution_id, api)
    mirror = None
    if (retained / "dependencies.tar.gz").exists():
        mirror = restore_dependencies(retained / "dependencies.tar.gz", root, execution.outputs.path("work") / "dependencies")
    execution.environ.update(TF_WORKSPACE=backend.workspace, TF_IN_AUTOMATION="1", TF_INPUT="0")
    cloud_init = [sys.executable, "-m", "iaas_automation.pve_inventory.cloud_init"]
    arguments = ["--tfvars", str(retained / "inputs.tfvars.json"), "--output-dir", str(retained / "snippets"),
                 "--storage-id", target["storage_id"], "--pve-host", target["ssh_host"], "--ssh-user", target["ssh_user"],
                 "--ssh-config", str(Path(execution.environ["HOME"]) / ".ssh/config"),
                 "--ssh-port", str(target.get("ssh_port", 22))]
    snippets = load_rendered_artifacts(retained / "snippets", target["storage_id"], retained / "inputs.tfvars.json", allow_empty=True)
    if snippets:
        verify_helper_trust(target, selected.files)
    context = execution.outputs.path("work") / "execution-context.json"
    _write(context, {"execution_admission": admission, "execution_id": execution_id,
                     "plan_sha256": metadata["plan_digest"], "target": target})
    result = {"schema_version": 1, "execution_id": execution_id, "plan_digest": metadata["plan_digest"],
              "target": target, "runtime": image_digest, "backend": backend.identity(), "root_id": scope,
              "phase": "running", "effects": {"facility": "none", "state": "none", "collection": "none"},
              "native_execution": {"status": "not_attempted"}, "state_persistence": {"status": "not_attempted"},
              "verification": {"status": "not_attempted"}, "collection": {"status": "not_attempted"},
              "verification_requirements": metadata["verification_requirements"],
              "guest": {"status": "not_attempted"}, "business": {"status": "not_performed"},
              "caller_acceptance": "incomplete" if any(r["required"] and r["responsibility"] != "iaas"
                                                        for r in metadata["verification_requirements"]["requirements"]) else "not_required",
              "recovery_of": admission.get("recovery_of"), "state_before": before.to_dict()}
    result_path = execution.outputs.root / "pve-result.json"
    _write(result_path, validate_result(result))
    try:
        result["effects"]["state"] = "unknown"
        _write(result_path, result)
        native_init = backend.initialize(root, execution.environ, execution.outputs.path("recovery"), tofu, plugin_dir=mirror)
        execution.record("backend-init", native_init, root)
        initialized = observe_state(backend, execution.environ)
        _state_transition(before.to_dict(), initialized.to_dict(), allow_initialization=True)
        admit_state(backend, state_admission, initialized)
        result["effects"]["state"] = "known"
        # Caller serialization spans these checks, snippet upload and native apply.
        _admit_templates(metadata, selected, execution_id, api)
        if snippets:
            result["effects"]["facility"] = "unknown"
            _write(result_path, result)
            execution.run("upload-snippets", [*cloud_init, "upload", *arguments, "--execution-context", str(context)], root)
            result["effects"]["facility"] = "known"
            result["snippet_upload"] = "completed"
            execution.run("verify-snippets", [*cloud_init, "verify", *arguments], root)
        result["native_execution"] = {"status": "unknown"}
        result["state_persistence"] = {"status": "unknown"}
        result["effects"]["facility"] = "unknown"
        _write(result_path, result)
        execution.run("apply", [tofu, "apply", "-input=false", "-lock-timeout=30s", str(retained / "plan.tfplan")], root)
        result["native_execution"] = {"status": "success"}
        if execution.phases[-1].get("recovery_file"):
            result["state_persistence"] = {"status": "failed"}
            require(False, "native recovery state prevents persistence confirmation")
        result["state_persistence"] = {"status": "passed", "basis": "complete_native_success"}
        result["effects"]["facility"] = "known"
        result["collection"] = {"status": "unknown"}
        _write(result_path, result)
        snapshot = observe_state(backend, execution.environ)
        _state_transition(initialized.to_dict(), snapshot.to_dict())
        require(snapshot.status == "present", "post-apply state collection failed")
        result["state_after"] = snapshot.to_dict()
        result["snapshot"] = snapshot.raw
        result["expectations"] = expectations(metadata["changes"], snapshot.raw)
        result["collection"] = {"status": "passed"}
        result["effects"]["collection"] = "known"
        _write(result_path, result)
        result["verification"] = verify_configuration(result["expectations"], api)
        result["phases"] = execution.phases
        result["phase"] = "succeeded" if result["verification"]["status"] == "passed" else "failed"
        _write(result_path, validate_result(result))
        require(result["phase"] == "succeeded", "saved-plan configuration verification incomplete")
        execution.finish({"operation": "apply", "execution_id": execution_id, "native_lifecycle": "success",
                          "caller_acceptance": result["caller_acceptance"]})
    except BaseException:
        result["phase"] = "failed"
        if execution.phases and execution.phases[-1]["phase"] == "apply":
            phase = execution.phases[-1]
            if phase.get("exit_code") and phase.get("capture_complete") and not phase.get("interrupted"):
                result["native_execution"] = {"status": "failed"}
                if phase.get("recovery_file"):
                    result["state_persistence"] = {"status": "failed"}
        result["phases"] = execution.phases
        try:
            _write(result_path, result)
        except OSError:
            # The launcher must retain storage if no complete result can be collected.
            execution.phases.append({"phase": "result-export", "retain_storage": True})
        raise


def verify_pve(plan: Path, bundle: Path, selected: SelectedConfig, execution: Execution,
               scope: str, image_digest: str) -> None:
    metadata = _json(bundle / "summary.json")
    metadata, _ = admit_plan(plan, bundle, target_selection(selected, scope, image_digest), None)
    require("verification_requirements" not in selected.options
            or _verification(selected) == metadata["verification_requirements"], "verification requirements cannot change after plan")
    if "execution_result" not in selected.files:
        report = {"status": "unknown", "reason": "original_execution_material_missing"}
    else:
        original = validate_result(_json(selected.files["execution_result"]))
        require(original.get("plan_digest") == metadata["plan_digest"] and original["target"] == metadata["target"]
                and original.get("backend") == metadata["backend"] and original["runtime"] == metadata["runtime"]
                and original.get("root_id") == metadata["root_id"]
                and original["verification_requirements"] == metadata["verification_requirements"],
                "original execution association conflict")
        require(not selected.options.get("execution_id") or original["execution_id"] == selected.options["execution_id"],
                "original execution identity conflict")
        snapshot = original.get("snapshot")
        if snapshot is not None:
            from .pve_state import workspace_state_key
            state_target = {"bucket": metadata["backend"]["bucket"],
                            "key": workspace_state_key(metadata["backend"], metadata["workspace"]),
                            "workspace": metadata["workspace"], "endpoint": metadata["backend"]["endpoint"]}
            require(isinstance(snapshot, dict) and isinstance(original.get("state_after"), dict)
                    and all(snapshot.get(k) == original["state_after"].get(k) for k in ("lineage", "serial"))
                    and all(original["state_after"].get(k) == v for k, v in state_target.items()),
                    "original state snapshot association conflict")
        expected = expectations(metadata["changes"], snapshot)
        if original.get("expectations") is not None:
            require(expected == original["expectations"], "original expectation material conflict")
        report = (verify_configuration(expected, api_client(metadata["target"], execution.environ)) if snapshot is not None
                  else {"status": "unknown", "reason": "original_state_snapshot_missing"})
        report.update(execution_id=original["execution_id"], original_native_execution=original["native_execution"],
                      original_phase=original["phase"], original_state_persistence=original["state_persistence"],
                      original_collection=original["collection"],
                      caller_acceptance=original.get("caller_acceptance", "incomplete"))
    _write(execution.outputs.path("diagnostics") / "verification.json", report)
    require(report["status"] == "passed", "saved-plan configuration verification incomplete")
    execution.finish({"operation": "verify", "configuration": report["status"], "historical_success_inferred": False,
                      **{k: v for k, v in report.items() if k.startswith("original_")}})


def read_pve(selected: SelectedConfig, execution: Execution, backend: S3Backend,
             scope: str, image_digest: str) -> None:
    from .pve_state import observe_state
    from .pve_results import state_instances
    target = target_selection(selected, scope, image_digest)
    observation = observe_state(backend, execution.environ)
    report = {"schema_version": 1, "target": target["target"], "backend": backend.identity(),
              "state": observation.to_dict(include_raw=True), "historical_success": "unknown", "objects": []}
    api = api_client(target["target"], execution.environ)
    for rows in state_instances(observation.raw or {}).values():
        for row in rows:
            value = row.get("attributes", {})
            node, vmid = value.get("node_name"), value.get("vm_id")
            if not node or not isinstance(vmid, int):
                continue
            try:
                report["objects"].append({"node": node, "vmid": vmid, "configuration": api.vm_config(node, vmid)})
            except Exception:
                report["objects"].append({"node": node, "vmid": vmid, "status": "unknown"})
    if "execution_result" in selected.files:
        original = validate_result(_json(selected.files["execution_result"]))
        require(original["target"] == target["target"] and original.get("backend") == backend.identity()
                and original.get("root_id") == scope,
                "original execution association conflict")
        require(not selected.options.get("execution_id") or original["execution_id"] == selected.options["execution_id"],
                "original execution identity conflict")
        report["original_result"] = original
    _write(execution.outputs.path("diagnostics") / "observation.json", report)
    require(observation.status != "error", "state read failed")
    execution.finish({"operation": "read", "state_observation": observation.status, "historical_success_inferred": False})

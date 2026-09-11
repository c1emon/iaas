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


def sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def target_selection(selected: SelectedConfig, scope: str, image_digest: str) -> dict[str, Any]:
    require(re.fullmatch(r"[^@]+@sha256:[0-9a-f]{64}", image_digest), "saved plans require a resolved image digest")
    root = selected.options.get("root", {})
    require(isinstance(root, dict) and scope and scope == root.get("id"),
            "PVE scope must explicitly select the complete declared root id")
    target = selected.options.get("pve", {})
    require(isinstance(target, dict) and set(target) == {"storage_id", "ssh_host", "ssh_user"},
            "PVE plan requires explicit storage_id, ssh_host and ssh_user")
    require(all(isinstance(value, str) and value for value in target.values()), "PVE target fields must be strings")
    require(re.fullmatch(r"[A-Za-z0-9_.:\[\]-]+", target["ssh_host"])
            and re.fullmatch(r"[a-z_][a-z0-9_-]*", target["ssh_user"]), "invalid PVE SSH target")
    return {"environment": selected.environment, "scenario": selected.scenario, "scope": scope,
            "root_id": root["id"], "image_digest": image_digest, "runtime_platform": runtime_platform(), "target": target}


def prepare_plan(selected: SelectedConfig, execution: Execution, backend: S3Backend,
                 scope: str, image_digest: str, tofu: str = "tofu") -> Path:
    metadata = target_selection(selected, scope, image_digest)
    generated = compile_documents(selected)
    bundle = execution.outputs.path("plan")
    root = materialize_root(selected.options["root"], selected.files, bundle / "workspace")
    tfvars = bundle / "inputs.tfvars.json"
    write_text(tfvars, generated["pve.tfvars.json"], secure=True)
    snippets = bundle / "snippets"
    storage = metadata["target"]["storage_id"]
    execution.run("render-snippets", [sys.executable, "-m", "iaas_automation.pve_inventory.cloud_init", "render",
                                      "--tfvars", str(tfvars), "--output-dir", str(snippets), "--storage-id", storage], root)
    mirror = None
    if "dependencies" in selected.files:
        shutil.copyfile(selected.files["dependencies"], bundle / "dependencies.tar.gz")
        (bundle / "dependencies.tar.gz").chmod(0o600)
        mirror = restore_dependencies(bundle / "dependencies.tar.gz", root, execution.outputs.path("work") / "dependencies")
    execution.environ.update(TF_WORKSPACE=backend.workspace, TF_IN_AUTOMATION="1", TF_INPUT="0")
    result = backend.initialize(root, execution.environ, execution.outputs.path("recovery"), tofu, plugin_dir=mirror)
    execution.record("backend-init", result, root)
    plan = bundle / "plan.tfplan"
    execution.run("plan", [tofu, "plan", "-input=false", "-lock-timeout=30s", f"-var-file={tfvars}", f"-out={plan}"], root)
    require(plan.is_file(), "successful tool exit did not produce a native plan")
    plan.chmod(0o600)
    review = execution.run("review", [tofu, "show", "-no-color", str(plan)], root)
    shutil.copyfile(review.capture, bundle / "review.txt")
    (bundle / "review.txt").chmod(0o600)
    manifest_file = manifest_path(snippets)
    manifest = json.loads(manifest_file.read_text())
    manifest["plan_sha256"] = sha256(plan)
    write_text(manifest_file, json.dumps(manifest, indent=2) + "\n", secure=True)
    metadata.update(schema_version=1, backend=backend.identity(),
                    root_directory=str(root.relative_to(bundle)),
                    provider_lock_sha256=sha256(root / ".terraform.lock.hcl"),
                    input_origins=sorted(map(str, selected.reader.logical_sources)))
    write_text(bundle / "summary.json", json.dumps(metadata, indent=2) + "\n", secure=True)
    # Initialization state and provider caches are not part of the transferable
    # root. The separate dependency archive supplies locked tools for later init.
    if (root / ".terraform").exists():
        shutil.rmtree(root / ".terraform")
    (root / "zz_iaas_backend_override.tf.json").unlink()
    execution.finish({"operation": "prepare-plan", "environment": selected.environment,
                      "plan": str(plan), "authorization": "application requires explicit caller selection"})
    return plan


def admit_plan(plan: Path, bundle: Path, expected: dict[str, Any], backend: S3Backend) -> tuple[dict[str, Any], Path]:
    protected_file(plan)
    metadata = json.loads((bundle / "summary.json").read_text())
    require(metadata.get("schema_version") == 1, "unsupported saved-plan metadata")
    require(all(metadata.get(key) == value for key, value in expected.items()), "saved plan target or runtime mismatch")
    require(metadata.get("backend") == backend.identity(), "saved plan backend/workspace mismatch")
    root = bundle.joinpath(*relative_path(metadata["root_directory"]).parts)
    require(root.resolve().is_relative_to(bundle.resolve()), "saved root escapes companion directory")
    require(sha256(root / ".terraform.lock.hcl") == metadata.get("provider_lock_sha256"), "saved provider lock mismatch")
    manifest = json.loads(manifest_path(bundle / "snippets").read_text())
    require(isinstance(manifest.get("plan_sha256"), str) and sha256(plan) == manifest["plan_sha256"],
            "native plan does not match companion manifest")
    load_rendered_artifacts(bundle / "snippets", metadata["target"]["storage_id"], bundle / "inputs.tfvars.json", allow_empty=True)
    return metadata, root


def apply_saved_plan(plan: Path, bundle: Path, selected: SelectedConfig, execution: Execution,
                     backend: S3Backend, scope: str, image_digest: str, tofu: str = "tofu") -> None:
    expected = target_selection(selected, scope, image_digest)
    # Admission before copying, init, upload or any other infrastructure write.
    metadata, _ = admit_plan(plan, bundle, expected, backend)
    require(not any(path.is_symlink() for path in bundle.rglob("*")), "saved companion directory contains a symlink")
    retained = execution.outputs.path("plan") / "selected"
    shutil.copytree(bundle, retained)
    shutil.copyfile(plan, retained / "plan.tfplan")
    for path in retained.rglob("*"):
        path.chmod(0o700 if path.is_dir() else 0o600 | (path.stat().st_mode & 0o100))
    _, root = admit_plan(retained / "plan.tfplan", retained, expected, backend)
    mirror = None
    if (retained / "dependencies.tar.gz").exists():
        mirror = restore_dependencies(retained / "dependencies.tar.gz", root, execution.outputs.path("work") / "dependencies")
    execution.environ.update(TF_WORKSPACE=backend.workspace, TF_IN_AUTOMATION="1", TF_INPUT="0")
    result = backend.initialize(root, execution.environ, execution.outputs.path("recovery"), tofu, plugin_dir=mirror)
    execution.record("backend-init", result, root)
    target = metadata["target"]
    cloud_init = [sys.executable, "-m", "iaas_automation.pve_inventory.cloud_init"]
    arguments = ["--tfvars", str(retained / "inputs.tfvars.json"), "--output-dir", str(retained / "snippets"),
                 "--storage-id", target["storage_id"], "--pve-host", target["ssh_host"], "--ssh-user", target["ssh_user"]]
    snippets = load_rendered_artifacts(retained / "snippets", target["storage_id"], retained / "inputs.tfvars.json", allow_empty=True)
    if snippets:
        execution.run("upload-snippets", [*cloud_init, "upload", *arguments], root)
        execution.run("verify-snippets", [*cloud_init, "verify", *arguments], root)
    execution.run("apply", [tofu, "apply", "-input=false", "-lock-timeout=30s", str(retained / "plan.tfplan")], root)
    execution.finish({"operation": "apply-saved-plan", "environment": selected.environment,
                      "known_effects": (["snippets uploaded and verified"] if snippets else []) + ["native saved plan applied"]})

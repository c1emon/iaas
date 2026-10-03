"""Durable local association for one-shot PVE operations; never a global ledger."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast

from iaas.common.errors import require
from iaas.pve_acceptance_contracts import (
    canonical_digest, load_strict_json, RuntimeIdentity,
    validate_acceptance_request, validate_acceptance_result,
    validate_snippet_cleanup_request, validate_snippet_cleanup_result,
)
from iaas.runtime_execution.pve_contracts import validate_execution_admission


def save(path: Path, value: dict[str, Any]) -> None:
    """Atomically replace protected material and flush it before a mutation."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)


def confined(root: Path, relative: str) -> Path:
    part = Path(relative)
    require(not part.is_absolute() and bool(part.parts) and ".." not in part.parts,
            "execution evidence reference is not confined")
    require(root.is_dir() and not root.is_symlink(), "execution evidence directory is unavailable")
    current = root
    for item in part.parts:
        current = current / item
        require(not current.is_symlink(), "execution evidence symlinks are forbidden")
    require(current.is_file(), "execution evidence file is unavailable")
    return current


def begin(root: Path, operation: str, request: dict[str, Any], admission: dict[str, Any],
          execution_id: str, image_digest: str, *, preview: dict[str, Any] | None = None) -> dict[str, Any]:
    validator = _request_validator(operation)
    request = validator(request)
    RuntimeIdentity.model_validate({"image_digest": image_digest})
    digest = canonical_digest(request)
    if operation == 'accept':
        from .acceptance_plan import validate_preview
        from .one_shot_admission import validate_one_shot_admission
        preview = validate_preview(preview, request=request)
        admission = validate_one_shot_admission(admission, request=request, preview=preview,
                    execution_id=execution_id, image_digest=image_digest, vmids=[request['temporary_vm']['vmid']])
    else:
        admission = validate_execution_admission(admission, digest=digest.removeprefix("sha256:"),
                                                 execution_id=execution_id, target=request["target"])
    require(admission.get('deadlines') == request['deadlines'], 'execution admission deadlines conflict')
    require(image_digest, "resolved runtime image digest is required")
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    marker = root / "started"
    fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    journal = {"kind": "pve-one-shot-journal", "schema_version": 1, "operation": operation,
               "execution_id": execution_id, "request_digest": digest, "target": request["target"],
               "admission": admission, "runtime": {"image_digest": image_digest},
               "deadlines": request['deadlines'], "facility_writes": "none",
               "status": "running", "mutation_active": False, "tasks": [], "resources": {}}
    if operation == 'accept':
        require(preview is not None, 'acceptance preview required')
        preview = cast(dict[str, Any], preview)
        journal.update(preview=preview, preview_digest=preview['preview_digest'], clone_marker=preview['clone_marker'])
        save(root / 'preview.json', preview)
    save(root / "request.json", request)
    save(root / "journal.json", journal)
    return journal


def observe(root: Path, operation: str, request: dict[str, Any] | None,
            execution_id: str) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Validate existing facts. Missing files raise; the caller reports unknown."""
    original = load_strict_json(confined(root, "request.json"))
    journal = load_strict_json(confined(root, "journal.json"))
    require(isinstance(original, dict) and isinstance(journal, dict), "invalid execution evidence")
    require(journal.get("kind") == "pve-one-shot-journal" and type(journal.get("schema_version")) is int and journal.get("schema_version") == 1
            and journal.get("operation") == operation, "original execution operation conflicts")
    require(not execution_id or journal.get("execution_id") == execution_id,
            "original execution identity conflicts")
    original = _request_validator(operation)(original)
    RuntimeIdentity.model_validate(journal.get("runtime"))
    digest = canonical_digest(original)
    require(journal.get("request_digest") == digest and journal.get("target") == original.get("target"),
            "original execution request binding conflicts")
    require(journal.get('deadlines') == original['deadlines']
            and journal.get('admission', {}).get('deadlines') == original['deadlines'],
            'original execution deadline binding conflicts')
    if request is not None:
        require(canonical_digest(request) == digest, "observed request conflicts with original execution")
    if operation == 'accept':
        preview = load_strict_json(confined(root, 'preview.json'))
        validate_acceptance_materials(original, journal)
        require(preview == journal['preview'], 'original preview snapshot conflicts')
    else:
        validate_execution_admission(journal.get("admission"), digest=digest.removeprefix("sha256:"),
                                     execution_id=journal["execution_id"], target=journal["target"])
    result = None
    if (root / "result.json").exists():
        result = load_strict_json(confined(root, "result.json"))
        require(isinstance(result, dict) and result.get("execution_id") == journal["execution_id"]
                and result.get("request_digest") == digest
                and result.get("runtime") == journal.get("runtime"), "original result binding conflicts")
        require(result.get('deadlines') == original['deadlines']
                and result.get('facility_writes') == journal.get('facility_writes'),
                'original result deadline/write facts conflict')
        if operation == 'accept':
            require(result.get('preview_digest') == journal['preview_digest']
                    and result.get('cluster_scope') == original['cluster_scope']
                    and result.get('pool') == original['temporary_vm']['pool']
                    and result.get('vmid_policy') == original['vmid_policy'], 'original result preview/policy binding conflicts')
        if result.get("overall") == "unknown":
            require(journal.get("status") in {"running", "interrupted", "finished"}
                    and type(journal.get("mutation_active")) is bool,
                    "original unknown result has invalid activity evidence")
        else:
            require(journal.get("status") == "finished" and journal.get("mutation_active") is False,
                    "original result has no terminal journal")
        require(journal.get("result_digest") == canonical_digest(result), "original result digest conflicts")
        result = (_result_validator(operation))(result)
    return journal, result


def validate_acceptance_materials(request: dict[str, Any], journal: dict[str, Any]) -> None:
    """Validate current acceptance snapshots for observation and snippet consumers."""
    from .acceptance_plan import validate_preview
    from .one_shot_admission import validate_one_shot_admission

    request = validate_acceptance_request(request)
    preview = validate_preview(journal.get('preview'), request=request)
    require(journal.get('request_digest') == canonical_digest(request)
            and journal.get('preview_digest') == preview['preview_digest']
            and journal.get('target') == request['target']
            and journal.get('deadlines') == request['deadlines']
            and journal.get('runtime') == request['runtime'], 'original acceptance snapshot binding conflicts')
    validate_one_shot_admission(journal.get('admission'), request=request, preview=preview,
        execution_id=journal['execution_id'], image_digest=journal['runtime']['image_digest'],
        vmids=[request['temporary_vm']['vmid']])


def _request_validator(operation: str):
    require(operation in {"accept", "snippet-cleanup"}, "unsupported one-shot operation")
    return validate_acceptance_request if operation == "accept" else validate_snippet_cleanup_request


def _result_validator(operation: str):
    require(operation in {"accept", "snippet-cleanup"}, "unsupported one-shot operation")
    return validate_acceptance_result if operation == "accept" else validate_snippet_cleanup_result

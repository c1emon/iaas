"""Synthetic tests for the protected K3s runtime secret channel."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from iaas_automation.common.errors import ValidationError
from iaas_automation.k3s_automation.secrets import (
    ProtectedSecretChannel,
    SecretMetadata,
    load_protected_environment_json,
    validate_external_secret_ref,
)

REFERENCE = "op://synthetic/k3s/server-token"
SECRET = "synthetic-runtime-secret"


def protected_json(path: Path, document: object) -> Path:
    path.write_text(json.dumps(document), encoding="utf-8")
    path.chmod(0o600)
    return path


def test_channel_resolves_exact_external_reference_and_returns_redacted_metadata(
    tmp_path: Path,
) -> None:
    path = protected_json(tmp_path / "runtime.json", {REFERENCE: SECRET})

    channel = load_protected_environment_json(path)
    metadata = channel.resolve(REFERENCE)

    assert isinstance(metadata, SecretMetadata)
    assert metadata.reference == REFERENCE
    assert metadata.source == "protected_environment_json"
    assert metadata.status == "resolved"
    assert SECRET not in repr(metadata)
    assert SECRET not in str(metadata)
    assert SECRET not in json.dumps(metadata.as_dict())


def test_secret_is_only_available_to_consumer_and_never_channel_result(
    tmp_path: Path,
) -> None:
    channel = load_protected_environment_json(
        protected_json(tmp_path / "runtime.json", {REFERENCE: SECRET})
    )
    observed: list[str] = []

    result = channel.consume(REFERENCE, observed.append)

    assert observed == [SECRET]
    assert isinstance(result, SecretMetadata)
    assert SECRET not in repr(result)


def test_consumer_return_value_is_discarded_to_prevent_secret_escape(
    tmp_path: Path,
) -> None:
    channel = load_protected_environment_json(
        protected_json(tmp_path / "runtime.json", {REFERENCE: SECRET})
    )

    result = channel.consume(REFERENCE, lambda value: value)

    assert isinstance(result, SecretMetadata)
    assert SECRET not in repr(result)


def test_consumer_failures_are_context_only_and_do_not_disclose_secret(
    tmp_path: Path,
) -> None:
    channel = load_protected_environment_json(
        protected_json(tmp_path / "runtime.json", {REFERENCE: SECRET})
    )

    def failing_consumer(value: str) -> None:
        raise RuntimeError(value)

    with pytest.raises(ValidationError) as excinfo:
        channel.consume(REFERENCE, failing_consumer)

    assert SECRET not in str(excinfo.value)


@pytest.mark.parametrize(
    "document",
    [
        {},
        {REFERENCE: ""},
        {REFERENCE: 123},
        {"K3S_SERVER_TOKEN": SECRET},
        {"op://synthetic/k3s/server-token": SECRET, "unexpected": "value"},
    ],
)
def test_missing_or_unsafe_environment_entries_fail_closed(
    tmp_path: Path, document: object
) -> None:
    path = protected_json(tmp_path / "runtime.json", document)

    with pytest.raises(ValidationError):
        load_protected_environment_json(path)


def test_environment_json_must_be_protected(tmp_path: Path) -> None:
    path = tmp_path / "runtime.json"
    path.write_text(json.dumps({REFERENCE: SECRET}), encoding="utf-8")
    path.chmod(0o644)

    with pytest.raises(ValidationError, match="restrictive permissions"):
        load_protected_environment_json(path)


def test_environment_json_symlink_is_not_accepted(tmp_path: Path) -> None:
    target = protected_json(tmp_path / "target.json", {REFERENCE: SECRET})
    link = tmp_path / "runtime.json"
    link.symlink_to(target)

    with pytest.raises(ValidationError, match="regular file"):
        load_protected_environment_json(link)


@pytest.mark.parametrize(
    "reference",
    [
        "",
        "synthetic-runtime-secret",
        "op://vault",
        "op:///item/field",
        "op://vault/item",
        "op://vault/item/field?leak=1",
        "op://vault/item/field#fragment",
        "op://user:password@vault/item/field",
        "op://vault:123/item/field",
        "op://vault/item//field",
        "op://vault/item/field/extra/last",
        "op://vault/item/field with-space",
    ],
)
def test_only_valid_external_references_are_admitted(reference: str) -> None:
    with pytest.raises(ValidationError):
        validate_external_secret_ref(reference)


def test_missing_reference_is_rejected_without_disclosing_reference_value(
    tmp_path: Path,
) -> None:
    channel = load_protected_environment_json(
        protected_json(tmp_path / "runtime.json", {REFERENCE: SECRET})
    )
    missing = "op://synthetic/k3s/missing"

    with pytest.raises(ValidationError) as excinfo:
        channel.resolve(missing)

    assert missing not in str(excinfo.value)
    assert SECRET not in str(excinfo.value)


def test_loader_does_not_read_process_environment_or_invoke_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = protected_json(tmp_path / "runtime.json", {REFERENCE: SECRET})
    monkeypatch.setenv("K3S_SERVER_TOKEN", "must-not-be-read")
    monkeypatch.setattr(os, "environ", {"K3S_SERVER_TOKEN": "must-not-be-read"})

    channel = load_protected_environment_json(path)

    assert channel.resolve(REFERENCE).status == "resolved"

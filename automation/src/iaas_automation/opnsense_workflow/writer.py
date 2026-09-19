"""Small adapter for the fixed OPNsense Collection write stages.

The workflow planner owns selection, ordering and admission.  ``Writer`` only
turns an already selected standard resource set into the arguments consumed by
the pinned Collection and records the two provider stages independently.  The
executor is deliberately injected: this module does not create an HTTP client
or expose arbitrary API paths.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from typing import Any, Protocol

import yaml

from iaas_automation.common.io import load_json, write_text
from iaas_automation.opnsense_validation import TOP_LEVEL, validate_document
from iaas_automation.opnsense_validation.lifecycle import resource_arguments


SUPPORTED_RESOURCES = (
    "aliases",
    "vips",
    "gateways",
    "filter-rules",
    "dnat",
    "one-to-one-nat",
    "interface-groups",
)


class WriterError(ValueError):
    """Raised when a stage cannot be admitted locally."""


class ProviderExecutor(Protocol):
    """The small boundary implemented by the Ansible stage adapter.

    ``save`` must pass ``reload=False`` to each Collection CRUD module.  The
    returned mapping is the module/stage result and may include ``changed`` or
    a provider response.  ``activate`` invokes the resource's fixed native
    activation target and must not retry it.
    """

    def save(
        self,
        resource: str,
        records: Sequence[Mapping[str, Any]],
        *,
        reload: bool,
        context: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]: ...

    def activate(self, resource: str) -> Mapping[str, Any]: ...


class _AnsibleProvider:
    """Run the repository's stage playbook and consume its protected result."""

    def __init__(self, execution: Any, target: Mapping[str, Any]) -> None:
        self.execution = execution
        self.target = dict(target)
        self._stage_number = 0
        if not isinstance(self.target.get("host"), str) or not isinstance(self.target.get("endpoint"), str):
            raise WriterError("workflow writer needs a resolved target host and endpoint")

    def _run(self, action: str, resource: str, records: Sequence[Mapping[str, Any]] | None = None,
             context: Mapping[str, Any] | None = None) -> dict[str, Any]:
        self._stage_number += 1
        stage_number = self._stage_number
        root = self.execution.outputs.path("work") / "opnsense-workflow"
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        result_path = root / f"{stage_number}-{action}-{resource}-result.json"
        inventory = root / "inventory.yml"
        variables = root / f"{action}-{resource}-vars.json"
        inventory_doc = {
            "all": {
                "children": {
                    "opnsense": {"hosts": {self.target["host"]: {}}}
                }
            }
        }
        write_text(inventory, yaml.safe_dump(inventory_doc, sort_keys=False), secure=True)
        values: dict[str, Any] = {
            "opnsense_workflow_resource": resource,
            "opnsense_workflow_action": action,
            "opnsense_api_host": self.target["endpoint"],
            "opnsense_ssl_verify": self.target.get("ssl_verify", True),
            # Credentials remain in the protected execution environment and
            # are resolved by Ansible at runtime, never written to this file.
            "opnsense_api_key": "{{ lookup('ansible.builtin.env', 'OPNSENSE_API_KEY') }}",
            "opnsense_api_secret": "{{ lookup('ansible.builtin.env', 'OPNSENSE_API_SECRET') }}",
            "opnsense_workflow_result_path": str(result_path),
        }
        try:
            result_path.unlink(missing_ok=True)
        except OSError:
            return {"status": "unknown", "error": "unable to clear prior stage result"}
        if action == "save":
            if records is None:
                raise WriterError("save stage requires selected records")
            source = root / f"{resource}-records.yml"
            document: dict[str, Any] = {RESOURCE_SPECS[resource].key: list(records)}
            if context is not None:
                document["opnsense_filter_rule_context"] = dict(context)
            write_text(source, yaml.safe_dump(document, sort_keys=False), secure=True)
            values["opnsense_workflow_source"] = str(source)
        write_text(variables, json.dumps(values), secure=True)
        command = [
            str(Path(sys.executable).parent / "ansible-playbook"),
            "-i", str(inventory), "--limit", f"localhost,{self.target['host']}",
            "-e", f"@{variables}",
            str(Path(__file__).resolve().parents[4] / "automation/ansible/playbooks/opnsense/workflow-stage.yml"),
        ]
        phase = f"opnsense-workflow-{action}-{resource}"
        error: Exception | None = None
        try:
            self.execution.run(phase, command, root)
        except Exception as exc:
            error = exc
        try:
            facts = load_json(result_path)
            if not isinstance(facts, dict):
                raise ValueError("workflow stage result is not a mapping")
        except Exception:
            return {"status": "unknown" if error is None else "failed", "error": "stage result unavailable"}
        if error is not None:
            return {"status": facts.get("status", "failed"), "result": facts}
        return {"status": facts.get("status", "unknown"), "changed": facts.get("changed", False), "result": facts}

    def save(self, resource: str, records: Sequence[Mapping[str, Any]], *, reload: bool,
             context: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        if reload:
            raise WriterError("workflow save always disables provider reload")
        return self._run("save", resource, records, context)

    def activate(self, resource: str) -> Mapping[str, Any]:
        return self._run("activate", resource)


@dataclass(frozen=True)
class ResourceSpec:
    """Fixed Collection mapping for one supported resource class."""

    key: str
    save_module: str
    activation_target: str
    shared_activation: bool = False


RESOURCE_SPECS: dict[str, ResourceSpec] = {
    "aliases": ResourceSpec("opnsense_aliases", "alias_multi", "alias"),
    "vips": ResourceSpec("opnsense_vips", "interface_vip", "interface_vip"),
    "gateways": ResourceSpec("opnsense_gateways", "gateway", "gateway"),
    "filter-rules": ResourceSpec("opnsense_filter_rules", "rule_multi", "rule"),
    "dnat": ResourceSpec("opnsense_dnat_rules", "nat_destination", "nat_destination"),
    "one-to-one-nat": ResourceSpec(
        "opnsense_one_to_one_nat_rules", "nat_one_to_one", "nat_one_to_one"
    ),
    "interface-groups": ResourceSpec(
        "opnsense_interface_groups",
        "rule_interface_group",
        "rule_interface_group",
        shared_activation=True,
    ),
}


def resource_spec(resource: str) -> ResourceSpec:
    try:
        return RESOURCE_SPECS[resource]
    except KeyError as error:
        raise WriterError(f"unsupported OPNsense workflow resource: {resource}") from error


def _as_records(resource: str, records: Sequence[Mapping[str, Any]],
                *, context: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    if isinstance(records, (str, bytes)) or not isinstance(records, Sequence):
        raise WriterError(f"{resource} records must be a sequence")
    try:
        values = [dict(record) for record in records]
    except (TypeError, ValueError) as error:
        raise WriterError(f"{resource} records must contain mappings") from error
    try:
        document: dict[str, Any] = {TOP_LEVEL[resource]: deepcopy(values)}
        if context is not None:
            document["opnsense_filter_rule_context"] = deepcopy(dict(context))
        validate_document(resource, document)
    except (KeyError, TypeError, ValueError) as error:
        raise WriterError(f"invalid {resource} records: {error}") from error
    return values


def _filter_rule_arguments(record: Mapping[str, Any]) -> dict[str, Any]:
    """Mirror the existing rule playbook's provider conversion."""

    item = dict(record)
    item["description"] = f"iaas:opnsense:filter:{item['scope']}:{item['slug']}"
    item["source_invert"] = item.get("source_invert", False)
    item["destination_invert"] = item.get("destination_invert", False)
    for field in ("source_net", "source_port", "destination_net", "destination_port"):
        value = item.get(field)
        if isinstance(value, list):
            item[field] = ",".join(str(part) for part in value)
        elif field.endswith("_port") and value is None:
            item[field] = ""
    item.pop("scope", None)
    item.pop("slug", None)
    return item


def provider_arguments(resource: str, record: Mapping[str, Any], *,
                       context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return one fixed-Collection CRUD argument mapping.

    The source records are copied and validated first.  In particular this
    keeps the existing NAT identity/argument rules in one place and preserves
    the direct playbook's provider mapping.
    """

    resource_spec(resource)
    selected = _as_records(resource, [record], context=context)[0]
    record = selected
    if resource == "aliases":
        return dict(record)
    if resource == "vips":
        return {
            "description": record["description"],
            "interface": record["interface"],
            "address": record["address"],
            "bind": record["bind"],
            "expand": record["expand"],
            "mode": "ipalias",
            "state": record["state"],
            "reload": False,
        }
    if resource == "gateways":
        return {**dict(record), "reload": False}
    if resource == "filter-rules":
        return _filter_rule_arguments(record)
    return resource_arguments(dict(record), resource)


def _status_from_error(error: BaseException) -> str:
    # A provider timeout/cancellation means that persistence cannot be safely
    # concluded.  Keep this separate from an explicit provider failure.
    return "unknown" if isinstance(error, (TimeoutError, ConnectionError)) else "failed"


def _provider_status(raw: Mapping[str, Any], *, activation: bool, resource: str | None = None) -> str:
    explicit = raw.get("status")
    if not activation and explicit == "accepted":
        return "saved" if raw.get("changed", True) else "unchanged"
    if explicit in {"accepted", "confirmed", "unconfirmed", "failed", "unknown"}:
        return str(explicit)
    if raw.get("failed") or raw.get("failed_when"):
        return "failed"
    if activation:
        # A controller response is provider/request evidence only.  The
        # executor must supply independent active-state evidence before this
        # status can become confirmed.
        if raw.get("active_confirmed") is True:
            return "confirmed"
        # The fixed group endpoint reports request acceptance only.  Keep that
        # fact distinct from an active confirmation; a caller may also choose
        # to normalize it to unconfirmed after its own active check.
        return "accepted" if resource == "interface-groups" else "unconfirmed"
    if raw.get("changed") is False:
        return "unchanged"
    return "saved"


class Writer:
    """Execute one selected resource stage through an injected provider.

    ``save`` and ``activate`` are intentionally separate calls.  No implicit
    activation, retry or rollback is performed here; the caller can stop
    dependent stages after an ``unconfirmed``/``failed`` result.
    """

    def __init__(self, provider: ProviderExecutor | Any | None = None,
                 target: Mapping[str, Any] | None = None, *,
                 execution: Any | None = None,
                 documents: Mapping[str, Any] | None = None) -> None:
        # Runtime integration passes Execution plus its resolved target.  Unit
        # and caller adapters may inject the smaller ProviderExecutor directly.
        if execution is not None:
            if provider is not None:
                raise WriterError("provide either provider or execution, not both")
            provider = execution
        self.provider = _AnsibleProvider(provider, target) if target is not None else provider
        self.documents = documents or {}

    def save(self, resource: str, records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        spec = resource_spec(resource)
        context = None
        source_document = self.documents.get(resource)
        if resource == "filter-rules" and isinstance(source_document, Mapping):
            candidate_context = source_document.get("opnsense_filter_rule_context")
            if isinstance(candidate_context, Mapping):
                context = candidate_context
        selected = _as_records(resource, records, context=context)
        # Validate/normalize the fixed Collection mapping before invoking the
        # executor, while passing the original standard records to the stage
        # adapter.  The Ansible stage performs the mapping itself; provider
        # arguments such as ``reload`` must not be written into the standard
        # source file and then revalidated as candidate fields.
        [provider_arguments(resource, record, context=context) for record in selected]
        arguments = selected
        result: dict[str, Any] = {
            "resource": resource,
            "module": spec.save_module,
            "attempted": bool(arguments),
            "records": len(arguments),
            "changed": False,
            "status": "unchanged" if not arguments else "unknown",
            "save": {"status": "unchanged" if not arguments else "unknown"},
            "configuration": {"status": "not_attempted"},
            "activation": {"status": "not_attempted"},
            "active_check": {"status": "not_attempted"},
        }
        if not arguments:
            return result
        if self.provider is None:
            raise WriterError("a provider executor is required to save a non-empty stage")
        try:
            if context is not None and isinstance(self.provider, _AnsibleProvider):
                raw = dict(self.provider.save(resource, arguments, reload=False, context=context))
            else:
                raw = dict(self.provider.save(resource, arguments, reload=False))
        except Exception as error:  # preserve the stage boundary for callers
            status = _status_from_error(error)
            result["status"] = status
            result["save"] = {"status": status, "error": str(error)}
            result["configuration"] = {"status": "unknown"}
            return result
        status = _provider_status(raw, activation=False, resource=resource)
        changed = bool(raw.get("changed", True))
        result["changed"] = changed
        result["status"] = status
        result["save"] = {"status": status, "changed": changed}
        result["configuration"] = {"status": "not_attempted"}
        if raw.get("error"):
            result["save"]["error"] = raw["error"]
        return result

    def activate(self, resource: str) -> dict[str, Any]:
        spec = resource_spec(resource)
        result: dict[str, Any] = {
            "resource": resource,
            "target": spec.activation_target,
            "shared_activation": spec.shared_activation,
            "attempted": True,
            "status": "unknown",
            "activation": {"status": "unknown"},
            "active_check": {"status": "not_attempted"},
        }
        if self.provider is None:
            raise WriterError("a provider executor is required to activate a stage")
        try:
            raw = dict(self.provider.activate(resource))
        except Exception as error:  # do not retry or hide partial saves
            status = _status_from_error(error)
            result["status"] = status
            result["activation"] = {"status": status, "error": str(error)}
            return result
        status = _provider_status(raw, activation=True, resource=resource)
        result["status"] = status
        result["activation"] = {"status": status}
        if raw.get("error"):
            result["activation"]["error"] = raw["error"]
        if raw.get("active_check") is not None:
            result["active_check"] = dict(raw["active_check"])
        return result


__all__ = [
    "ProviderExecutor",
    "RESOURCE_SPECS",
    "SUPPORTED_RESOURCES",
    "ResourceSpec",
    "Writer",
    "WriterError",
    "provider_arguments",
    "resource_spec",
]

"""Adapters to existing component operations; no generic mutation passthrough."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Any, cast

import yaml

from iaas_automation.common.errors import require
from iaas_automation.common.io import write_text
from iaas_automation.runtime_config import SelectedConfig
from iaas_automation.runtime_config.compile import compile_documents
from .execution import Execution


IMPLEMENTATION = Path(__file__).resolve().parents[4]


def _inputs(selected: SelectedConfig, execution: Execution) -> dict[str, Path]:
    directory = execution.outputs.path("work") / "inputs"
    result = {}
    for name, value in selected.documents.items():
        path = directory / f"{name}.yml"
        write_text(path, yaml.safe_dump(value, sort_keys=False), secure=True)
        result[name] = path
    return result


def _playbook(execution: Execution, phase: str, inventory: Path, scope: str,
              playbook: str, variables: dict[str, Any]) -> None:
    values = execution.outputs.path("work") / f"{phase}-vars.json"
    write_text(values, json.dumps(variables), secure=True)
    # OPNsense's existing admission contract selects exactly OPNSENSE_TARGET
    # and rejects --limit, which could skip its localhost admission play.
    limit = [] if playbook == "opnsense/diagnostics.yml" else ["--limit", f"localhost,{scope}"]
    execution.run(phase, [str(Path(sys.executable).parent / "ansible-playbook"), "-i", str(inventory),
                         *limit, "-e", f"@{values}",
                         str(IMPLEMENTATION / "automation/ansible/playbooks" / playbook)], execution.outputs.path("work"))


def _inventory_scope(inventory: dict[str, Any], group: str, scope: str) -> None:
    require(bool(re.fullmatch(r"[A-Za-z0-9_.-]+(?:,[A-Za-z0-9_.-]+)*", scope)), "explicit host names are required")
    selected = scope.split(",")
    require(len(selected) == len(set(selected)) and not set(selected) & {"all", "localhost", "ungrouped"}, "invalid diagnostic scope")
    members: set[str] = set()

    def visit(node: dict[str, Any], within: bool = False) -> None:
        if within:
            members.update(node.get("hosts", {}))
        for name, child in node.get("children", {}).items():
            visit(child, within or name == group)

    visit(inventory.get("all", {}))
    if group in inventory:
        visit(inventory[group], True)
    require(set(selected) <= members, "scope includes hosts outside the selected component")


def run_component(selected: SelectedConfig, operation: str, scope: str, execution: Execution) -> None:
    component = selected.component
    require(bool(scope), "online operations require explicit scope")
    if component in {"pve", "foundation", "k3s"}:
        generated = compile_documents(selected)
        inputs = _inputs(selected, execution)
    else:
        generated, inputs = {}, {}
    if component == "pve":
        require(scope == selected.documents["cluster"]["cluster"]["name"], "PVE diagnostic scope must explicitly name the complete cluster")
        execution.run(operation, [sys.executable, "-m", f"iaas_automation.pve_inventory.{operation}",
                                  "--cluster", str(inputs["cluster"]), "--vms", str(inputs["vms"])], execution.outputs.path("work"))
    elif component == "foundation":
        require(scope == selected.environment, "foundation health scope must explicitly name the declared environment")
        # Caller declares any CA dependency by its original logical path.
        inventory = selected.documents["inventory"]
        for service in inventory.get("foundation_services", []):
            check = service.get("health_check", {})
            if check.get("ca_file"):
                alias = selected.options.get("ca_files", {}).get(check["ca_file"])
                require(alias in selected.files, "foundation CA file must be explicitly supplied")
                check["ca_file"] = str(selected.files[alias])
        inputs = _inputs(selected, execution)
        execution.run("health", [sys.executable, "-m", "iaas_automation.foundation_inventory.cli",
                                  "--inventory", str(inputs["inventory"]), "--health"], execution.outputs.path("work"))
    elif component == "k3s":
        from iaas_automation.k3s_automation.config import build_composed_model
        from iaas_automation.k3s_automation.operations import validate_deployment_scope, validate_exact_scope
        model = build_composed_model(selected.documents["intent"], selected.documents["inventory"])
        (validate_deployment_scope if operation == "deploy" else validate_exact_scope)(model, scope)
        review = execution.outputs.path("work") / "k3s-review.yml"
        write_text(review, generated["k3s-review.yml"], secure=True)
        variables: dict[str, Any] = {"k3s_model_path": str(review), f"k3s_{operation}_scope": scope}
        if operation == "preflight":
            mode = selected.options.get("preflight_mode")
            require(mode in {"install", "converge", "upgrade"}, "K3s preflight_mode must be explicit")
            variables.update(k3s_preflight_mode=mode, k3s_runtime_secret_file=str(selected.files["runtime_secrets"]))
        elif operation == "deploy":
            variables.update(k3s_deploy_model_path=str(review), k3s_deploy_runtime_secret_file=str(selected.files["runtime_secrets"]))
        elif operation == "upgrade":
            from iaas_automation.k3s_automation.operations import validate_upgrade
            version = selected.options.get("upgrade_target")
            require(isinstance(version, str) and bool(version), "K3s upgrade_target must be explicit")
            observations = selected.files["observed_versions"]
            plan = validate_upgrade(model, scope, json.loads(observations.read_text()), cast(str, version))
            upgrade_plan = execution.outputs.path("work") / "upgrade-plan.json"
            write_text(upgrade_plan, json.dumps({"scope": list(plan.scope), "target_version": plan.target_version,
                                                "skipped": list(plan.skipped), "to_upgrade": list(plan.to_upgrade)}), secure=True)
            variables.update(k3s_upgrade_model_path=str(review), k3s_upgrade_target_version=version,
                             k3s_upgrade_observed_versions_path=str(observations), k3s_upgrade_plan_path=str(upgrade_plan),
                             k3s_upgrade_runtime_secret_file=str(selected.files["runtime_secrets"]))
        _playbook(execution, operation, inputs["inventory"], scope, f"k3s/{operation}.yml", variables)
    elif component in {"opnsense", "switch"}:
        inventory = yaml.safe_load(selected.files["inventory"].read_text())
        require(isinstance(inventory, dict), "diagnostic inventory must be a mapping")
        _inventory_scope(inventory, "switches" if component == "switch" else component, scope)
        require(component != "opnsense" or "," not in scope, "OPNsense diagnostics requires exactly one target")
        path = execution.outputs.path("work") / "environment/inventory.yml"
        write_text(path, yaml.safe_dump(inventory, sort_keys=False), secure=True)
        if component == "opnsense":
            request = yaml.safe_load(selected.files["request"].read_text())
            require(isinstance(request, dict), "diagnostic request must be a mapping")
            detail = (str(execution.outputs.path("diagnostics") / "runtime/opnsense-diagnostics/detail.json")
                      if request.get("include_details") is True else "")
            execution.environ.update(OPNSENSE_TARGET=scope, OPNSENSE_DIAGNOSTICS_REQUEST=str(selected.files["request"]),
                                      OPNSENSE_DIAGNOSTICS_OUTPUT=detail, OUTPUT_DIR=str(execution.outputs.path("diagnostics")),
                                      ENVIRONMENT_DIR=str(path.parent))
            variables = {"opnsense_api_key": "{{ lookup('env', 'OPNSENSE_API_KEY') }}",
                         "opnsense_api_secret": "{{ lookup('env', 'OPNSENSE_API_SECRET') }}"}
            _playbook(execution, "diagnose", path, scope, "opnsense/diagnostics.yml", variables)
        else:
            variables = {"ansible_user": "{{ lookup('env', 'SWITCH_SSH_USER') }}",
                         "ansible_password": "{{ lookup('env', 'SWITCH_SSH_PASSWORD') }}",
                         "ansible_port": "{{ lookup('env', 'SWITCH_SSH_PORT') | default('22', true) }}",
                         "switch_export_dir": str(execution.outputs.path("diagnostics") / "{{ inventory_hostname }}")}
            _playbook(execution, "diagnose", path, scope, "switches/readonly-facts.yml", variables)
    else:
        require(False, "unsupported online component operation")
    execution.finish({"component": component, "operation": operation, "scope": scope})

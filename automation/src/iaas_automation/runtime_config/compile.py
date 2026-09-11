"""Compile selected documents through existing domain validators and renderers."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile

import yaml

from iaas_automation.common.errors import ValidationError, require
from .loader import SelectedConfig


def compile_documents(selected: SelectedConfig) -> dict[str, str]:
    """Return non-sensitive derived outputs without touching the filesystem."""
    docs = selected.documents
    component = selected.component
    required = {
        "pve": {"cluster", "vms"}, "services": {"services", "vms"},
        "foundation": {"inventory"}, "k3s": {"intent", "inventory"},
    }
    require(required.get(component, set()) <= docs.keys(), "required component input is missing")
    # Existing domain exceptions sometimes quote invalid values. Keep those
    # details out of the public runtime error channel.
    try:
        if component == "pve":
            from iaas_automation.pve_inventory.inventory.validation.cluster import validate_cluster
            from iaas_automation.pve_inventory.inventory.validation.vm import validate_vms
            from iaas_automation.pve_inventory.inventory.model import build_model
            from iaas_automation.pve_inventory.inventory.render import render_outputs
            cluster = validate_cluster(docs["cluster"])
            result = render_outputs(build_model(cluster, validate_vms(docs["vms"], cluster)))
            return {"pve.tfvars.json": result["tfvars"], "pve-inventory.yml": result["ansible"],
                    "pve.md": result["docs"], "template-build.env": result["template_build_env"]}
        if component == "services":
            from iaas_automation.services_inventory.validation import load_vm_names, validate_services
            from iaas_automation.services_inventory.model import build_model
            from iaas_automation.services_inventory.render import build_markdown
            services, warnings = validate_services(docs["services"], load_vm_names(docs["vms"]))
            return {"services.md": build_markdown(build_model(services, warnings))}
        if component == "foundation":
            from iaas_automation.foundation_inventory.validation import validate_foundation_inventory
            from iaas_automation.foundation_inventory.model import build_model
            from iaas_automation.foundation_inventory.render import build_markdown
            return {"foundation.md": build_markdown(build_model(validate_foundation_inventory(docs["inventory"])))}
        if component == "k3s":
            from iaas_automation.k3s_automation.config import build_composed_model, render_review
            return {"k3s-review.yml": render_review(build_composed_model(docs["intent"], docs["inventory"]))}
        if component == "opnsense":
            from iaas_automation.opnsense_validation import RESOURCE_FILES, validate_document
            require(docs.keys() <= RESOURCE_FILES.keys(), "unsupported OPNsense input")
            for resource, document in docs.items():
                validate_document(resource, document)
            return {RESOURCE_FILES[name]: yaml.safe_dump(value, sort_keys=False) for name, value in docs.items()}
        if component == "switch":
            require(set(docs) == {"config"}, "switch requires a config input")
            implementation = Path(__file__).resolve().parents[4]
            validation = implementation / "automation/ansible/roles/switch_config/tasks/validate.yml"
            with tempfile.TemporaryDirectory(prefix="iaas-switch-check-") as temp:
                directory = Path(temp)
                variables = directory / "inputs.yml"
                variables.write_text(yaml.safe_dump(docs["config"]))
                variables.chmod(0o600)
                playbook = directory / "check.yml"
                playbook.write_text(yaml.safe_dump([{
                    "name": "Check selected switch inputs offline", "hosts": "localhost",
                    "gather_facts": False, "connection": "local",
                    "vars": {"switch_config_allowed_states": ["merged"]},
                    "tasks": [{"ansible.builtin.import_tasks": str(validation)}],
                }]))
                result = subprocess.run([
                    str(Path(sys.executable).parent / "ansible-playbook"),
                    "-i", "localhost,", "--skip-tags", "runtime-credentials",
                    "-e", f"@{variables}", str(playbook),
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                require(result.returncode == 0, "switch configuration validation failed")
            return {"switch-config.yml": yaml.safe_dump(docs["config"], sort_keys=False)}
    except (ValidationError, KeyError, TypeError, ValueError):
        raise ValidationError(f"{component}: selected inputs failed domain validation") from None
    raise ValidationError("component compiler is not available")


def export_generated(selected: SelectedConfig, implementation: Path, output: Path) -> list[str]:
    """Export only domain-produced files after all validation and overlap checks."""
    selected.protect_outputs(implementation, output)
    generated = compile_documents(selected)
    # Existing files are not guessed to be generated; caller selects a fresh
    # destination. A second invocation can explicitly select another directory.
    require(not output.exists(), "export destination must not already exist")
    output.mkdir(parents=True, mode=0o755)
    for name, contents in generated.items():
        (output / name).write_text(contents, encoding="utf-8")
    return list(generated)

"""Static first-release operation table and operation-specific environment."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Mapping

from iaas_automation.common.errors import require
from iaas_automation.runtime_config.selection import runtime_platform
from .state import PVE_ENV, S3_ENV
from .pve_contracts import PLAN_METADATA_VERSION, RESULT_VERSION


@dataclass(frozen=True)
class Operation:
    network: bool = False
    state: bool = False
    infrastructure_write: bool = False
    local_write: bool = True


OFFLINE = Operation()
DIAGNOSE = Operation(network=True)
MUTATE = Operation(network=True, infrastructure_write=True)
PLAN = Operation(network=True, state=True)
APPLY = Operation(network=True, state=True, infrastructure_write=True)
OPERATIONS = {
    "opnsense": {"check": OFFLINE, "generate": OFFLINE, "diagnose": DIAGNOSE,
                  # The configuration workflow talks to the appliance but
                  # owns no OpenTofu/S3 state.  A plan is therefore an online
                  # read with private local output, while apply is the only
                  # operation in this group that can mutate infrastructure.
                  "read": DIAGNOSE, "plan": DIAGNOSE, "apply": MUTATE,
                  "verify": DIAGNOSE},
    "switch": {"check": OFFLINE, "generate": OFFLINE, "diagnose": DIAGNOSE},
    "pve": {"check": OFFLINE, "generate": OFFLINE, "preflight": DIAGNOSE,
            "health": DIAGNOSE, "prepare-dependencies": DIAGNOSE,
            "read": PLAN, "plan": PLAN, "apply": APPLY, "verify": DIAGNOSE},
    "pve-template": {"check": OFFLINE, "read": DIAGNOSE, "plan": DIAGNOSE,
                     "apply": MUTATE, "verify": OFFLINE},
    "image": {"check": OFFLINE, "build": Operation(network=True), "test": Operation(network=True),
              "read": OFFLINE, "verify": OFFLINE, "clean": OFFLINE},
    "services": {"check": OFFLINE, "generate": OFFLINE},
    "foundation": {"check": OFFLINE, "generate": OFFLINE, "health": DIAGNOSE},
    "k3s": {"check": OFFLINE, "generate": OFFLINE, "render": OFFLINE,
            "preflight": DIAGNOSE, "verify": DIAGNOSE,
            "deploy": MUTATE, "snapshot": MUTATE, "upgrade": MUTATE},
}


def operation_for(component: str, operation: str) -> Operation:
    if component == "pve" and operation in {"prepare-plan", "apply-saved-plan"}:
        require(False, "prepare-plan/apply-saved-plan were removed; use PVE plan/apply")
    require(component in OPERATIONS and operation in OPERATIONS[component], "unsupported component/operation combination")
    return OPERATIONS[component][operation]


def capabilities() -> dict[str, Any]:
    return {"interface_version": 1, "schema_versions": [1], "platforms": [runtime_platform()],
            "lifecycle_versions": {
                "pve": {"plan": PLAN_METADATA_VERSION, "result": RESULT_VERSION},
                "pve-template": {"preview": 2, "result": 2, "record": 2},
                "image": {"artifact": 1, "build_request": 1, "test_request": 1, "test_result": 1},
            },
            "operations": {component: {name: asdict(value) for name, value in entries.items()}
                           for component, entries in OPERATIONS.items()}}


def credential_names(component: str, operation: str, render_names: tuple[str, ...] = ()) -> set[str]:
    effects = operation_for(component, operation)
    if not effects.network or operation == "prepare-dependencies":
        return set()
    names: set[str] = set()
    if effects.state:
        names |= S3_ENV
    names |= {
        "pve": PVE_ENV,
        "pve-template": {"PVE_API_TOKEN", "PVE_API_CA"} | ({"PVE_ARTIFACT_URL"} if operation == "apply" else set()),
        "opnsense": {"OPNSENSE_API_KEY", "OPNSENSE_API_SECRET"},
        "switch": {"SWITCH_SSH_USER", "SWITCH_SSH_PASSWORD", "SWITCH_SSH_PORT"},
        "k3s": set(), "foundation": set(),
    }.get(component, set())
    if operation in {"plan"}:
        for name in render_names:
            require(re.fullmatch(r"[A-Z][A-Z0-9_]*", name) is not None
                    and not name.startswith(("OP_", "AWS_", "DOCKER_", "TF_"))
                    and name not in {"PATH", "HOME", "PYTHONPATH", "LD_PRELOAD", "BASH_ENV", "ENV"},
                    "cloud-init credential name conflicts with reserved runtime environment")
            names.add(name)
    return names


def process_environment(component: str, operation: str, supplied: Mapping[str, str],
                        render_names: tuple[str, ...] = ()) -> dict[str, str]:
    # These are set by the image/controller, not forwarded wholesale from hosts.
    runtime_names = {"PATH", "HOME", "PYTHONPATH", "ANSIBLE_CONFIG", "ANSIBLE_ROLES_PATH",
                     "ANSIBLE_COLLECTIONS_PATH", "ANSIBLE_FILTER_PLUGINS", "ANSIBLE_LOOKUP_PLUGINS",
                     "ANSIBLE_LOCAL_TEMP", "XDG_CACHE_HOME", "UV_NO_SYNC", "UV_PYTHON_DOWNLOADS",
                     "UV_NO_CACHE", "PYTHONDONTWRITEBYTECODE"}
    if component == "image" and operation in {"build", "test"}:
        # The dedicated image-builder installs Packer plugins outside the
        # execution HOME.  Keep that image-owned path when HOME is relocated
        # to the task workspace; do not expose it to unrelated components.
        runtime_names.add("PACKER_PLUGIN_PATH")
    allowed = runtime_names | credential_names(component, operation, render_names)
    return {name: value for name, value in supplied.items() if name in allowed}

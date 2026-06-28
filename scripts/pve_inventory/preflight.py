"""Facade/orchestration for read-only online PVE preflight.

This module keeps the public CLI surface small and delegates the actual
checks to focused helpers so tests can keep importing the stable facade
symbols from here.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from scripts.common.errors import ValidationError
from scripts.common.io import load_yaml

from .checks.preflight.api import ProxmoxAPI, create_api_client, run_api_checks
from .checks.preflight.model import DerivedResources, derive_expected_resources
from .checks.preflight.ssh import run_ssh_checks
from .checks.results import CheckResult, has_failures, render_report
from .inventory.model import build_model
from .paths import DEFAULT_CLUSTER, DEFAULT_VMS
from .pve_api.errors import redact_sensitive_text
from .pve_api.protocol import PveReadOnlyApi
from .pve_api.runtime import PveOnlineRuntimeContext, load_api_runtime_config, load_online_runtime_context
from .validation import validate_cluster, validate_vms


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse the tiny CLI surface used by the make targets."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cluster", type=Path, default=DEFAULT_CLUSTER, help="Path to inventory/pve-cluster.yml")
    parser.add_argument("--vms", type=Path, default=DEFAULT_VMS, help="Path to inventory/vms.yml")
    return parser.parse_args(argv)


def run_preflight(
    cluster_path: Path = DEFAULT_CLUSTER,
    vms_path: Path = DEFAULT_VMS,
    environ: dict[str, str] | None = None,
    api_client: PveReadOnlyApi | None = None,
    ssh_runner=None,
) -> list[CheckResult]:
    """Run the full read-only preflight and return structured results."""
    results: list[CheckResult] = []
    if api_client is None:
        load_api_runtime_config(environ)
    runtime: PveOnlineRuntimeContext = load_online_runtime_context(environ)

    cluster_doc = load_yaml(cluster_path)
    cluster_state = validate_cluster(cluster_doc)
    vms_doc = load_yaml(vms_path)
    vms = validate_vms(vms_doc, cluster_state)
    model = build_model(cluster_state, vms)
    expected: DerivedResources = derive_expected_resources(model)

    client = api_client or create_api_client(runtime)
    run_api_checks(runtime, client, model, expected, results)

    if ssh_runner is None:
        from subprocess import run as ssh_runner  # type: ignore[no-redef]
    run_ssh_checks(runtime, results, runner=ssh_runner)
    return results


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint; non-zero only when blocking failures are present."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        results = run_preflight(cluster_path=args.cluster, vms_path=args.vms)
    except ValidationError as exc:
        print(f"FAIL model.validation: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"FAIL preflight: {redact_sensitive_text(str(exc), [os.environ.get('TF_VAR_pve_api_token_secret', '')])}")
        return 1

    print(render_report(results), end="")
    return 1 if has_failures(results) else 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CheckResult",
    "ProxmoxAPI",
    "derive_expected_resources",
    "has_failures",
    "main",
    "parse_args",
    "render_report",
    "run_preflight",
]

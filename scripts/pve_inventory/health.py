"""Explicit online PVE cluster health checks."""

from __future__ import annotations

import argparse
import os
import sys
from typing import TYPE_CHECKING
from pathlib import Path

from scripts.common.errors import ValidationError

from .paths import DEFAULT_CLUSTER, DEFAULT_VMS
from .pve_api import HealthApiRuntimeConfig, PveReadOnlyApi, load_api_runtime_config, redact_sensitive_text
from .checks.health.core import run_health_checks
from .checks.results import has_failures, render_report

if TYPE_CHECKING:
    from .checks.results import CheckResult


def load_health_runtime_config(environ: dict[str, str] | None = None) -> HealthApiRuntimeConfig:
    return load_api_runtime_config(environ)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cluster", type=Path, default=DEFAULT_CLUSTER, help="Path to inventory/pve-cluster.yml")
    parser.add_argument("--vms", type=Path, default=DEFAULT_VMS, help="Path to inventory/vms.yml")
    return parser.parse_args(argv)


def run_health(
    cluster_path: Path = DEFAULT_CLUSTER,
    vms_path: Path = DEFAULT_VMS,
    environ: dict[str, str] | None = None,
    api_client: PveReadOnlyApi | None = None,
) -> list[CheckResult]:
    return run_health_checks(cluster_path=cluster_path, vms_path=vms_path, environ=environ, api_client=api_client)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        results = run_health(cluster_path=args.cluster, vms_path=args.vms)
    except ValidationError as exc:
        print(f"FAIL model.validation: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"FAIL health: {redact_sensitive_text(str(exc), [os.environ.get('TF_VAR_pve_api_token_secret', '')])}")
        return 1

    print(render_report(results), end="")
    return 1 if has_failures(results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

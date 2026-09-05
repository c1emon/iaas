"""Command entry point for platform handoff validation."""

from .cli import main
from iaas_automation.common.cli import run_validation_cli


if __name__ == "__main__":
    raise SystemExit(run_validation_cli(main))

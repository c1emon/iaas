"""Run the offline K3s automation CLI."""

from iaas_automation.common.cli import run_validation_cli

from .cli import main


raise SystemExit(run_validation_cli(main))

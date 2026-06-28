## Why

PVE preflight internals now live under `checks/preflight/`, but health check logic remains concentrated in the top-level `health.py` command facade. Splitting health internals into `checks/health/` will make current-state health checks easier to maintain while preserving the stable `scripts.pve_inventory.health` command surface.

## What Changes

- Introduce internal `scripts/pve_inventory/checks/health/` modules for PVE health check expectations and current-state check groups.
- Keep top-level `scripts.pve_inventory.health` as the stable CLI/facade and preserve its exported symbols used by tests and commands.
- Keep shared result/reporting primitives in `scripts.pve_inventory.checks.results`.
- Keep PVE API runtime/protocol/error behavior in `scripts.pve_inventory.pve_api/`; do not duplicate API adapter concerns in health modules.
- Preserve PVE health result IDs, severity semantics, runtime parsing, report output, and exit behavior.
- Do not change PVE preflight semantics, inventory generation, cloud-init behavior, or default offline validation behavior.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `pve-inventory-package-organization`: Clarify that health current-state helpers may be organized under `checks/health/` while the stable health command facade remains top-level.

## Impact

- Affected code:
  - `scripts/pve_inventory/health.py` and any health-specific helper functions moved into `checks/health/`.
  - Tests importing health facade symbols or asserting health result IDs/severity/report behavior.
  - Online health checks that depend on `pve_api` read-only methods.
- Operational impact:
  - No new online access beyond explicit PVE health invocation.
  - No PVE mutation behavior.
  - Existing command entrypoints remain stable.
- Non-goals:
  - Combining health and preflight commands.
  - Changing health thresholds, result IDs, severity semantics, or exit-code policy.
  - Splitting cloud-init or offline inventory helpers in this change.

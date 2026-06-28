## Why

The first PVE inventory package reorganization grouped online check helpers under `checks/`, but the offline inventory generation, rendering, and validation code still lives in a mostly flat top-level package. Moving the offline inventory core into an `inventory/` subpackage will make the boundary between command facades, offline inventory modeling, online checks, and shared PVE API runtime code easier to understand before more PVE workflows accumulate.

## What Changes

- Introduce an internal `scripts/pve_inventory/inventory/` package for offline inventory model, render, and validation helpers.
- Move model/render/validation helper modules into responsibility-oriented paths such as `inventory/model.py`, `inventory/render.py`, and `inventory/validation/`.
- Preserve stable command-facing and test-facing facades including `scripts.pve_inventory.cli`, `scripts.pve_inventory.validation`, `scripts.pve_inventory.preflight`, `scripts.pve_inventory.health`, and `scripts.pve_inventory.cloud_init`.
- Keep `scripts/pve_inventory/pve_api/` as the shared online API/runtime/error/protocol boundary and do not move it under `inventory/`.
- Do not split `health.py` or `cloud_init.py` in this change.
- Do not change generated inventory output, validation semantics, online check behavior, cloud-init behavior, or default offline validation behavior.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `pve-inventory-package-organization`: Clarify that offline inventory model, rendering, and validation helpers are grouped separately from online checks and command facades.

## Impact

- Affected code:
  - `scripts/pve_inventory/model.py`, `render.py`, `validation.py`, `cluster_validation.py`, `vm_validation.py`, and `passthrough.py` import paths.
  - Top-level facades and commands that import offline inventory helpers.
  - Tests that import internal inventory validation/model/render helpers.
- Operational impact:
  - No new online access.
  - No PVE mutation behavior.
  - Existing Makefile/module entrypoints should continue to work.
- Non-goals:
  - Moving or duplicating `pve_api/`.
  - Further splitting `checks/`, `health.py`, or `cloud_init.py`.
  - Changing validation rules, generated files, or operator-facing command names.

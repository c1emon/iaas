## Why

`scripts/pve_inventory/` now contains inventory generation, validation, cloud-init helpers, PVE API adapters, preflight checks, and health checks in one mostly flat package. Recent PVE API/runtime consolidation made the online-check boundary clearer, so this is a good moment to organize the package by responsibility before more PVE workflows accumulate.

## What Changes

- Reorganize `scripts/pve_inventory/` into intent-oriented subpackages for online checks, inventory model/render/validation, and cloud-init support where useful.
- Keep stable command entrypoints such as `scripts.pve_inventory.cli`, `scripts.pve_inventory.preflight`, `scripts.pve_inventory.health`, and `scripts.pve_inventory.cloud_init` available for Makefile and operator workflows.
- Move online-check helper modules such as preflight API/model/SSH checks and shared check results under a `checks/` package.
- Optionally split large facade modules only when a thin compatibility entrypoint can preserve existing `python -m` behavior and test imports.
- Do not change PVE online preflight semantics, PVE health semantics, generated inventory outputs, cloud-init output content, or default offline validation behavior.
- Do not move PVE-domain logic into `scripts/common/`.

## Capabilities

### New Capabilities
- `pve-inventory-package-organization`: Defines internal package organization and stable public entrypoint expectations for the repository-owned PVE inventory tooling.

### Modified Capabilities
- None. This change is an internal structure refactor and should preserve existing operator-facing behavior.

## Impact

- Affected code:
  - `scripts/pve_inventory/` package structure and internal imports.
  - PVE preflight, health, inventory generation, cloud-init helper, and tests that import internal modules.
  - OpenSpec/main specs only for the new internal organization capability.
- Operational impact:
  - No new online access in default checks.
  - No PVE mutation behavior.
  - Existing root and PVE Makefile entrypoints should continue to work.
- Non-goals:
  - Changing check semantics or result IDs.
  - Renaming operator-facing commands.
  - Rewriting the PVE API adapter layer.
  - Combining preflight and health into one command.

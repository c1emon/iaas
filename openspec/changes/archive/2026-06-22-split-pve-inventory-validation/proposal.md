## Why

`scripts/pve_inventory/validation.py` now mixes shared schema helpers, cluster automation validation, VM normalization, and VM validation in one 500+ line module. Splitting it now reduces coupling before the P0 reliability work adds more validation entrypoints, checks, and future online preflight code.

## What Changes

- Split PVE inventory validation into focused modules for common helpers, cluster validation, and VM validation.
- Keep the existing `scripts.pve_inventory.validation` import surface as a compatibility façade for callers and tests.
- Update passthrough validation to import shared helpers from the common validation module instead of the façade.
- Preserve all current offline validation behavior, normalized output shapes, generated artifacts, and error messages unless an import path improvement requires only internal changes.
- Add or keep tests that prove the refactor is behavior-preserving.

## Capabilities

### New Capabilities
- `pve-inventory-validation-structure`: Covers the modular structure and compatibility requirements for PVE inventory validation code.

### Modified Capabilities
- `pve-automation-foundation`: Clarifies that offline inventory validation remains a stable, behavior-preserving boundary while implementation modules may be split internally.

## Impact

- Affected code: `scripts/pve_inventory/validation.py`, new validation submodules under `scripts/pve_inventory/`, and imports in `scripts/pve_inventory/passthrough.py`.
- Affected tests: existing PVE inventory tests under `scripts/tests/test_pve_inventory_phase3.py` should continue to pass without changing their public imports.
- No new runtime dependencies, CLI flags, generated output formats, or online PVE behavior.

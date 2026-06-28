## Why

`services_inventory` currently reuses primitive helpers from `scripts.pve_inventory`, making the PVE inventory package act as an implicit common layer for unrelated service metadata code. This makes future maintenance riskier: small PVE refactors can accidentally affect service inventory validation, and shared helper ownership is unclear.

This change extracts only boring Python primitives into an explicit `scripts/common/` layer so PVE and service inventory code can share error, I/O, validation, CLI-boundary, and Markdown table-cell helpers without creating domain coupling or a broad framework.

## What Changes

- Add a small `scripts/common/` Python package for reusable primitives only.
- Move shared validation error and assertion helpers out of `scripts/pve_inventory` ownership.
- Move basic YAML/JSON/text I/O helpers and generated-output stale checks into common primitives where they are domain-neutral.
- Move basic schema assertion helpers such as mapping/list/string/bool/int/unknown-key checks into common primitives.
- Optionally expose a thin CLI validation boundary helper that preserves the existing `FAIL validation: ...` stderr and exit-code contract.
- Optionally expose Markdown table-cell escaping as a common primitive when used at Markdown table boundaries.
- Update PVE inventory and services inventory code to depend on `scripts.common` for primitives.
- Remove `services_inventory` imports from `scripts.pve_inventory.*` internals.
- Preserve current commands, generated outputs, default offline behavior, and operator-visible validation error contracts.
- Do not move PVE, service inventory, cloud-init, PVE API, OPNsense, OpenTofu, Ansible, or renderer domain policy into common code.

## Capabilities

### New Capabilities
- `python-common-primitives`: Defines the explicit shared Python primitive layer, allowed helper categories, dependency direction, and behavior-preservation expectations for inventory tooling.

### Modified Capabilities
- None. Existing PVE inventory, service metadata, and validation entrypoint behavior should remain externally unchanged; this change introduces an internal shared primitive capability and preserves existing user-facing requirements.

## Impact

- Affected areas:
  - New `scripts/common/` package.
  - `scripts/pve_inventory/errors.py`, `scripts/pve_inventory/validation_common.py`, and `scripts/pve_inventory/io.py` import ownership or compatibility wrappers.
  - `scripts/services_inventory/io.py`, `scripts/services_inventory/validation.py`, `scripts/services_inventory/cli.py`, and possibly `scripts/services_inventory/render.py`.
  - Python tests that import `ValidationError`, load YAML, check stale outputs, assert Markdown escaping, or validate CLI failure boundaries.
- Operational impact:
  - No new online access or mutation behavior.
  - `make check` remains offline-safe.
  - Generated outputs should remain unchanged for unchanged source-of-truth files.
- Non-goals:
  - Broad domain directory reshuffling.
  - A generic inventory framework.
  - Merging PVE API clients or runtime adapters.
  - Changing validation semantics for PVE inventory or service metadata.
  - Changing root command names, CLI flags, success messages, failure prefix, or exit-code behavior.

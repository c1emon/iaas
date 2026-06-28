## Why

PVE online checks now have two read-only API paths: `pve-preflight` uses a small urllib client and `pve-health` uses a proxmoxer-backed facade. Their runtime environment parsing, safe error handling, redaction, and fake-client shapes are drifting even though both commands ask PVE for read-only facts.

This change consolidates the shared PVE API and runtime adapter boundaries so future online checks can reuse a consistent read-only facade without merging the distinct preflight and health semantics or forcing a risky backend rewrite.

## What Changes

- Add a repository-owned read-only PVE API protocol/facade boundary for online checks.
- Consolidate PVE API runtime environment parsing for endpoint, token credentials, TLS verification, and optional SSH adjunct context.
- Normalize safe PVE API exception types and redaction behavior across preflight and health paths.
- Update `pve-health` and `pve-preflight` to depend on the shared read-only facade shape and runtime parsing rather than separate ad hoc contracts.
- Keep preflight apply-readiness semantics and health current-state semantics separate.
- Keep online checks explicit and outside `make check` and cloud CI.
- Do not introduce mutation-capable PVE API helpers.
- Do not require the first refactor to delete the urllib backend or force all callers onto proxmoxer if a transitional adapter better preserves behavior.

## Capabilities

### New Capabilities
- `pve-api-runtime-adapters`: Defines the shared read-only PVE API facade/protocol, runtime config parsing, safe error/redaction contract, and backend-transition boundaries for repository-owned PVE online checks.

### Modified Capabilities
- None. Existing `pve-online-preflight` and PVE health operator-facing behavior should remain externally unchanged; this change introduces an internal adapter/runtime capability and preserves the explicit-online/offline-safe contracts.

## Impact

- Affected areas:
  - `scripts/pve_inventory/pve_api/` package structure and exports.
  - `scripts/pve_inventory/preflight_api.py` or a replacement/transitional adapter module.
  - `scripts/pve_inventory/preflight_config.py` and `scripts/pve_inventory/health.py` runtime config parsing.
  - `scripts/pve_inventory/preflight.py` and `scripts/pve_inventory/health.py` API injection/fake-client boundaries.
  - Python tests for PVE preflight, PVE health, API adapter errors, runtime config, redaction, and offline guards.
- Operational impact:
  - No new online access in default checks.
  - No PVE mutation behavior.
  - Existing `make pve-preflight` and `make pve-health` command semantics should remain unchanged.
- Non-goals:
  - Merging `pve-preflight` and `pve-health` commands.
  - Adding VM migration, node maintenance, reboot, package update, snippet upload, start/stop, or remediation operations.
  - Moving PVE API code into `scripts/common`.
  - Forcing immediate removal of the urllib backend before behavior is covered by tests.

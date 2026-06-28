## 1. Shared API runtime and error boundary

- [ ] 1.1 Add a shared PVE API runtime config module under `scripts/pve_inventory/pve_api/` for API credentials, TLS insecure mode, and optional SSH adjunct context.
- [ ] 1.2 Move or consolidate boolean runtime parsing so preflight and health accept the same boolean spellings and validation errors.
- [ ] 1.3 Normalize PVE API safe exception exports and redaction helpers so online checks consume `PveApiError` subclasses instead of backend-specific exceptions or generic runtime errors.
- [ ] 1.4 Preserve operator-safe missing-runtime-variable messages without printing token secrets or resolved credential values.

## 2. Read-only PVE API facade shape

- [ ] 2.1 Define a repository-owned read-only PVE API protocol or facade contract covering the facts used by both preflight and health checks.
- [ ] 2.2 Ensure the shared facade exposes named read-only methods rather than a broad generic mutation-capable client surface.
- [ ] 2.3 Extend the proxmoxer-backed adapter to provide any additional named read-only methods needed by preflight, such as node network, cluster VM resources, and PCI mapping reads.
- [ ] 2.4 Add a transitional urllib-backed adapter only if needed to preserve preflight behavior while satisfying the shared facade contract.
- [ ] 2.5 Keep PVE API code inside `scripts/pve_inventory/pve_api/` and do not move PVE-specific API behavior into `scripts/common/`.

## 3. Preflight and health migration

- [ ] 3.1 Update `scripts/pve_inventory/health.py` to use shared runtime config parsing and the shared read-only facade shape while preserving health semantics and result IDs.
- [ ] 3.2 Update `scripts/pve_inventory/preflight.py` and preflight API checks to use shared runtime config parsing and the shared read-only facade shape while preserving preflight readiness semantics and result IDs.
- [ ] 3.3 Preserve optional SSH adjunct behavior for preflight, including skipped behavior when SSH context is absent.
- [ ] 3.4 Keep `pve-health` and `pve-preflight` as separate explicit online commands and keep both outside default `make check` and cloud CI.
- [ ] 3.5 Remove or simplify obsolete duplicated runtime parsing or transport-specific code only after callers have migrated to the shared boundary.

## 4. Tests and verification

- [ ] 4.1 Add or update unit tests for shared runtime config parsing, including missing API variables, optional SSH context, and invalid boolean values.
- [ ] 4.2 Add or update tests proving token secrets are redacted from adapter exceptions, command reports, and validation failures.
- [ ] 4.3 Add fake-client tests showing preflight and health can consume the same read-only facade shape without mutation helpers.
- [ ] 4.4 Preserve existing PVE preflight behavior tests for nodes, bridges, storage, templates, VMID ownership, PCI mappings, SSH adjuncts, and offline guards.
- [ ] 4.5 Preserve existing PVE health behavior tests for reachability, quorum, node status/capacity, storage, templates, VM runtime state, HA, Ceph, redaction, and offline guards.
- [ ] 4.6 Run `uv run pytest scripts/tests/test_pve_preflight.py scripts/tests/test_pve_health.py` or a narrower equivalent while iterating.
- [ ] 4.7 Run `uv run pytest scripts/tests` after migration.
- [ ] 4.8 Run `make check` and confirm default validation remains offline-safe.
- [ ] 4.9 Run `openspec validate consolidate-pve-api-runtime-adapters`.

## 5. Optional manual online smoke

- [ ] 5.1 If PVE runtime credentials are available, run explicit `make pve-preflight` and confirm behavior matches the pre-refactor command semantics.
- [ ] 5.2 If PVE runtime credentials are available, run explicit `make pve-health` and confirm behavior matches the pre-refactor command semantics.
- [ ] 5.3 If runtime credentials are unavailable, document that online smoke was skipped and rely on fake-client coverage plus offline checks.

## 1. Common primitive package

- [x] 1.1 Create a small `scripts/common/` Python package with explicit primitive modules and no imports from PVE or services inventory packages.
- [x] 1.2 Move or expose the shared validation error type and `require` assertion helper from common primitives.
- [x] 1.3 Move or expose basic schema assertion helpers for mappings, lists, booleans, positive integers, non-empty strings, unknown-key rejection, and URL-like strings from common primitives.
- [x] 1.4 Move or expose YAML/JSON/text I/O primitives and domain-neutral stale/missing text-output comparison helpers from common primitives.
- [x] 1.5 Add a thin common CLI validation boundary helper only if it preserves the existing `FAIL validation: ...` stderr and exit-code behavior without owning argparse or domain orchestration.
- [x] 1.6 Add a common Markdown table-cell escaping primitive only if it can preserve current generated service documentation behavior exactly.

## 2. PVE inventory migration

- [x] 2.1 Update PVE inventory modules to import shared primitive behavior from `scripts.common` or from thin compatibility wrappers backed by `scripts.common`.
- [x] 2.2 Keep PVE-specific generated-output ordering, rendering, validation policy, cloud-init behavior, and online/runtime operations inside `scripts/pve_inventory`.
- [x] 2.3 Preserve existing PVE public validation/rendering entrypoints and generated output schemas.

## 3. Services inventory migration

- [x] 3.1 Update services inventory validation, I/O, CLI, and optional Markdown rendering code to use `scripts.common` for domain-neutral primitives.
- [x] 3.2 Remove direct services inventory imports from `scripts.pve_inventory.errors`, `scripts.pve_inventory.validation_common`, `scripts.pve_inventory.io`, or other PVE internals.
- [x] 3.3 Keep service schema policy, endpoint choices, exposure/auth choices, warning generation, and service documentation rendering policy inside `scripts/services_inventory`.

## 4. Tests and verification

- [x] 4.1 Update or add tests for common primitive helpers where behavior is now owned by `scripts.common`.
- [x] 4.2 Preserve existing tests for PVE inventory validation, service metadata validation, Markdown table escaping, stale-output checks, and CLI validation failure boundaries.
- [x] 4.3 Add or update an import-boundary assertion that `scripts/services_inventory` no longer imports `scripts.pve_inventory.*` internals for shared primitive behavior.
- [x] 4.4 Run `uv run pytest scripts/tests` or the repository's equivalent Python test target.
- [x] 4.5 Run `make check` and confirm it remains offline-safe.
- [x] 4.6 Confirm generated PVE outputs and `docs/generated/services.md` have no unexpected diff after the refactor.

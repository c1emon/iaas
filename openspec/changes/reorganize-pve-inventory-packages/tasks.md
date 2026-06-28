## 1. Online check package skeleton

- [ ] 1.1 Add `scripts/pve_inventory/checks/` package skeleton with preflight and health subpackages where needed.
- [ ] 1.2 Move shared check result/reporting primitives from `preflight_results.py` to `checks/results.py`.
- [ ] 1.3 Update preflight and health imports to use `checks.results` while preserving exported facade symbols where tests intentionally import them from command modules.

## 2. Preflight helper reorganization

- [ ] 2.1 Move `preflight_model.py` to `checks/preflight/model.py` and update all imports.
- [ ] 2.2 Move `preflight_api.py` to `checks/preflight/api.py` and update all imports.
- [ ] 2.3 Move `preflight_ssh.py` to `checks/preflight/ssh.py` and update all imports.
- [ ] 2.4 Keep top-level `preflight.py` as the stable CLI/facade entrypoint and ensure `python -m scripts.pve_inventory.preflight` behavior is unchanged.
- [ ] 2.5 Remove obsolete top-level helper modules after imports have migrated; do not leave thin compatibility shims unless a documented import surface requires one.

## 3. Health helper reorganization

- [ ] 3.1 Evaluate whether `health.py` can be mechanically split into `checks/health/core.py` plus a top-level CLI/facade.
- [ ] 3.2 If the split is mechanical, move health check internals into `checks/health/core.py` while preserving top-level `health.py` exports used by tests and commands.
- [ ] 3.3 If the split is not mechanical, leave `health.py` in place and document/defer health internals reorganization to a later change.
- [ ] 3.4 Preserve PVE health result IDs, severity semantics, runtime parsing, and exit behavior.

## 4. Import and behavior preservation

- [ ] 4.1 Update tests to import moved internal helpers from their new package paths.
- [ ] 4.2 Keep stable command-facing imports from `scripts.pve_inventory.preflight`, `scripts.pve_inventory.health`, `scripts.pve_inventory.cli`, and `scripts.pve_inventory.cloud_init` working.
- [ ] 4.3 Confirm no PVE-domain code is moved into `scripts/common/`.
- [ ] 4.4 Confirm `pve_api/` remains the shared API/runtime/error/protocol boundary and is not duplicated in check packages.

## 5. Verification

- [ ] 5.1 Run `uv run pytest scripts/tests/test_pve_preflight.py scripts/tests/test_pve_health.py scripts/tests/test_pve_api.py scripts/tests/test_pve_runtime.py` while iterating.
- [ ] 5.2 Run `uv run pytest scripts/tests` after package moves.
- [ ] 5.3 Run `make check` and confirm default validation remains offline-safe.
- [ ] 5.4 Run `openspec validate reorganize-pve-inventory-packages`.
- [ ] 5.5 If PVE runtime credentials are available and the implementation touched command facades beyond imports, optionally rerun explicit `pve-preflight` and `pve-health` smoke checks.

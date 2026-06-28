## 1. Health helper mapping

- [ ] 1.1 Switch to the implementation branch for `reorganize-pve-health-check-packages` before editing code.
- [ ] 1.2 Map current `scripts.pve_inventory.health` facade exports and tests that intentionally import them.
- [ ] 1.3 Group current health helpers by dependency shape before moving: expectations/model, core orchestration, node/storage, VM/template, HA/Ceph, and shared normalization utilities.

## 2. Health package skeleton and model move

- [ ] 2.1 Ensure `scripts/pve_inventory/checks/health/` has the needed package skeleton.
- [ ] 2.2 Move `HealthThresholds`, `HealthExpectations`, `THRESHOLDS`, and `derive_health_expectations` into `checks/health/model.py` and update imports.
- [ ] 2.3 Re-export stable model symbols from `scripts.pve_inventory.health` for existing facade imports.

## 3. Health internals reorganization

- [ ] 3.1 Move health check orchestration internals into `checks/health/core.py` while keeping `run_health` in the top-level facade.
- [ ] 3.2 If dependency mapping stays mechanical, split node/capacity/storage checks into a focused `checks/health/node.py` module.
- [ ] 3.3 If dependency mapping stays mechanical, split VM/template checks into a focused `checks/health/vm.py` module.
- [ ] 3.4 If dependency mapping stays mechanical, split HA/Ceph checks into a focused `checks/health/infra.py` module.
- [ ] 3.5 If any split creates circular imports or broad rewrites, keep that helper group in `core.py` and document the deferred split in this task file.

## 4. Facade and boundary preservation

- [ ] 4.1 Keep `scripts.pve_inventory.health` as the stable CLI/facade and preserve `python -m scripts.pve_inventory.health` behavior.
- [ ] 4.2 Preserve health facade exports used by tests and commands, including runtime loading, expectations, thresholds, `render_report`, and `run_health`.
- [ ] 4.3 Confirm `checks/health/*` imports shared result primitives from `checks.results`, not from the top-level health facade.
- [ ] 4.4 Confirm PVE API transport/runtime/error/protocol concerns remain in `pve_api/` and are not duplicated in health helper modules.
- [ ] 4.5 Preserve PVE health result IDs, severity semantics, report output, redaction behavior, runtime parsing, and exit behavior.

## 5. Tests and validation

- [ ] 5.1 Update tests that intentionally import moved internal helpers to use new `checks.health...` paths while keeping facade import tests intact.
- [ ] 5.2 Run focused tests: `uv run pytest scripts/tests/test_pve_health.py scripts/tests/test_pve_api.py scripts/tests/test_pve_runtime.py`.
- [ ] 5.3 Run online-check regression tests: `uv run pytest scripts/tests/test_pve_preflight.py scripts/tests/test_pve_health.py`.
- [ ] 5.4 Run `uv run pytest scripts/tests`.
- [ ] 5.5 Run `make check` and confirm default validation remains offline-safe.
- [ ] 5.6 Run `openspec validate reorganize-pve-health-check-packages`.

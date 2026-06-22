## 1. Module Extraction

- [x] 1.1 Create `scripts/pve_inventory/validation_common.py` and move shared assertion helpers into it without changing behavior or error messages.
- [x] 1.2 Create `scripts/pve_inventory/cluster_validation.py` and move `validate_automation()` and `validate_cluster()` into it.
- [x] 1.3 Create `scripts/pve_inventory/vm_validation.py` and move `parse_static_ip()`, VM normalization helpers, and `validate_vms()` into it.
- [x] 1.4 Replace `scripts/pve_inventory/validation.py` with a compatibility façade that re-exports the existing public helper and entrypoint names.

## 2. Import Cleanup

- [x] 2.1 Update `scripts/pve_inventory/passthrough.py` to import shared helpers from `validation_common.py` instead of the façade.
- [x] 2.2 Verify `scripts/pve_inventory/cli.py` and existing tests can continue importing `validate_cluster` and `validate_vms` from `scripts.pve_inventory.validation`.
- [x] 2.3 Check for and resolve any import cycles introduced by the split.

## 3. Behavior Preservation Checks

- [x] 3.1 Run `pytest scripts/tests/test_pve_inventory_phase3.py` and fix any regressions.
- [x] 3.2 Run `python scripts/validate_pve_inventory.py --check` and confirm generated artifacts remain up to date.
- [x] 3.3 Inspect the git diff to confirm no generated output or operator-facing validation behavior changed unexpectedly.

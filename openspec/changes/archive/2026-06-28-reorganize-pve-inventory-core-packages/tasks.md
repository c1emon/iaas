## 1. Package skeleton and import inventory

- [x] 1.1 Switch to the implementation branch for `reorganize-pve-inventory-core-packages` before editing code.
- [x] 1.2 Add `scripts/pve_inventory/inventory/` and `scripts/pve_inventory/inventory/validation/` package skeletons.
- [x] 1.3 Map all imports of `model.py`, `render.py`, `validation.py`, `cluster_validation.py`, `vm_validation.py`, and `passthrough.py` before moving files.

## 2. Offline inventory core module moves

- [x] 2.1 Move `scripts/pve_inventory/model.py` to `scripts/pve_inventory/inventory/model.py` and update imports.
- [x] 2.2 Move `scripts/pve_inventory/render.py` to `scripts/pve_inventory/inventory/render.py` and update imports.
- [x] 2.3 Move `scripts/pve_inventory/cluster_validation.py` to `scripts/pve_inventory/inventory/validation/cluster.py` and update imports.
- [x] 2.4 Move `scripts/pve_inventory/vm_validation.py` to `scripts/pve_inventory/inventory/validation/vm.py` and update imports.
- [x] 2.5 Move `scripts/pve_inventory/passthrough.py` to `scripts/pve_inventory/inventory/validation/passthrough.py` and update imports.
- [x] 2.6 Add an internal `scripts.pve_inventory.inventory.validation` aggregate only if it simplifies new internal imports without replacing the stable top-level validation facade.

## 3. Stable facade preservation

- [x] 3.1 Keep `scripts.pve_inventory.cli` as the stable inventory CLI entrypoint and preserve `python -m scripts.pve_inventory.cli` behavior.
- [x] 3.2 Keep `scripts.pve_inventory.validation` as the stable top-level validation facade and preserve exported validation helpers used by tests and commands.
- [x] 3.3 Update `scripts.pve_inventory.preflight` and `scripts.pve_inventory.health` imports only as needed for moved inventory helpers; preserve their command facades and exported symbols.
- [x] 3.4 Confirm `scripts.pve_inventory.cloud_init` remains unchanged except for imports if any are required.
- [x] 3.5 Remove obsolete top-level internal helper modules after imports migrate; do not leave compatibility shims unless a documented import surface requires one.

## 4. Boundary checks

- [x] 4.1 Confirm `scripts/pve_inventory/pve_api/` remains a sibling package and is not moved under `inventory/`.
- [x] 4.2 Confirm `scripts/pve_inventory/checks/` remains separate from offline inventory model/render/validation helpers.
- [x] 4.3 Confirm no PVE-domain code is moved into `scripts/common/`.
- [x] 4.4 Confirm `paths.py` and `secrets.py` remain top-level for this change unless implementation reveals a documented reason to pause and update artifacts.

## 5. Tests and validation

- [x] 5.1 Update tests that intentionally import moved internal helpers to use new `scripts.pve_inventory.inventory...` paths.
- [x] 5.2 Run focused tests covering inventory generation, validation, online preflight, health, API, and runtime behavior.
- [x] 5.3 Run `uv run pytest scripts/tests` after package moves.
- [x] 5.4 Run `make check` and confirm default validation remains offline-safe.
- [x] 5.5 Run `openspec validate reorganize-pve-inventory-core-packages`.

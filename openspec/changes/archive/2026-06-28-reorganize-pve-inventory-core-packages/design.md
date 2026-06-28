## Context

`scripts/pve_inventory/` now has a clearer online-check structure after the previous `checks/` refactor, but the offline inventory generation path is still represented by several top-level helper modules:

```text
scripts/pve_inventory/
├── cli.py                         stable inventory CLI facade
├── validation.py                  stable validation facade
├── model.py                       offline inventory model assembly
├── render.py                      generated output rendering
├── cluster_validation.py          cluster source validation
├── vm_validation.py               VM source validation
├── passthrough.py                 passthrough validation/normalization
├── checks/                        online check internals
├── pve_api/                       shared online API/runtime boundary
├── preflight.py / health.py       online command facades
└── cloud_init.py                  cloud-init command facade/tooling
```

The flat helper modules are all part of the offline inventory core, but their names sit next to command facades and online check packages. This makes the package harder to scan than it needs to be: maintainers have to infer whether a file is a command entrypoint, an internal inventory model helper, a validation helper, or online runtime code.

The desired next step is intentionally narrower than a full package redesign: create a clear `inventory/` subpackage for offline model/render/validation internals while leaving command facades and online runtime/check boundaries stable.

## Goals / Non-Goals

**Goals:**

- Group offline inventory model, rendering, and validation helpers under `scripts/pve_inventory/inventory/`.
- Preserve existing command-facing module entrypoints, especially `python -m scripts.pve_inventory.cli` and the Makefile validation targets.
- Preserve stable facade imports from `scripts.pve_inventory.validation` for tests and callers that intentionally use the top-level validation facade.
- Keep this as a mechanical import-path refactor with no changes to generated output, validation semantics, cloud-init behavior, or online check behavior.
- Keep `pve_api/` as the shared online API/runtime/error/protocol package outside the offline `inventory/` package.

**Non-Goals:**

- Do not move `cli.py`, `preflight.py`, `health.py`, or `cloud_init.py` into subpackages.
- Do not split `health.py` internals in this change.
- Do not split `cloud_init.py` internals in this change.
- Do not move `checks/` or `pve_api/` under `inventory/`.
- Do not introduce thin compatibility shims for old internal helper paths unless a documented import surface requires one.

## Decisions

### Decision: Move only the offline inventory core helpers

Move these modules into an internal package shape:

```text
scripts/pve_inventory/inventory/
├── __init__.py
├── model.py                       from scripts/pve_inventory/model.py
├── render.py                      from scripts/pve_inventory/render.py
└── validation/
    ├── __init__.py                internal validation aggregate
    ├── cluster.py                 from cluster_validation.py
    ├── vm.py                      from vm_validation.py
    └── passthrough.py             from passthrough.py
```

Rationale: these files form the offline inventory core and have a mostly mechanical dependency relationship. Grouping them creates a clear contrast with `checks/` for online checks and `pve_api/` for shared online API/runtime code.

Alternative considered: move all top-level helpers, including `paths.py` and `secrets.py`, into `inventory/`. Rejected for this change because `paths.py` is shared by command facades and `cloud_init.py`, while `secrets.py` is primarily tied to cloud-init user-data rendering and is better revisited with a dedicated cloud-init split.

### Decision: Keep top-level facades stable

Keep `cli.py` and `validation.py` at the top level. Update their internals to import from `inventory/`, but preserve their module paths and exported functions.

Rationale: `cli.py` is an operator-facing module entrypoint, and `validation.py` is a test-facing/source-facing aggregate. Moving them would add compatibility concerns that are not needed to improve internal organization.

Alternative considered: move `cli.py` to `inventory/cli.py` and leave a wrapper. Rejected because it adds a wrapper layer without changing behavior.

### Decision: Do not move `pve_api/`

Keep `scripts/pve_inventory/pve_api/` as a sibling of `inventory/` and `checks/`.

Rationale: `pve_api/` is not offline inventory modeling logic. It is the shared online API/runtime/error/protocol boundary used by preflight and health. Moving it under `inventory/` would blur the intended boundary and imply online API runtime is owned by inventory generation.

### Decision: Leave `health.py` and `cloud_init.py` for later changes

This change does not split `health.py` or `cloud_init.py`.

Rationale: `health.py` was previously evaluated as not a purely mechanical split, and `cloud_init.py` combines render, manifest, upload, verify, and CLI responsibilities. Either can be reorganized later, but both deserve their own behavior-preservation plan and tests.

## Risks / Trade-offs

- Import churn hides behavior drift → Run focused inventory/preflight/health tests plus full scripts tests and `make check`.
- Tests or local scripts import old internal helper paths directly → Update repository tests to new internal paths, keep top-level `validation.py` as the stable facade, and avoid old-path shims unless evidence shows a documented import surface.
- `paths.py` remains top-level while related inventory helpers move → Accept temporarily because `paths.py` is shared by facades and cloud-init; revisit only if later package boundaries make a better home obvious.
- `secrets.py` remains top-level → Accept temporarily because moving it with inventory would misclassify cloud-init-specific behavior.

## Migration Plan

1. Add `scripts/pve_inventory/inventory/` and `inventory/validation/` package skeletons.
2. Move offline helper modules into the new package paths.
3. Update `cli.py`, `validation.py`, `preflight.py`, `health.py`, `cloud_init.py` only as needed for imports; preserve command behavior.
4. Update tests that intentionally import internal helpers to use new package paths.
5. Remove obsolete top-level internal helper modules without adding shims unless a documented import surface requires one.
6. Run focused inventory and online-check tests, then the full scripts test suite, `make check`, and OpenSpec validation.

Rollback is straightforward: restore the moved modules to top-level paths and revert import updates. No infrastructure state, credentials, generated outputs, or live PVE resources are changed by this refactor itself.

## Open Questions

- Should `paths.py` remain a top-level shared constants module long-term, or eventually become a broader `config/paths.py` style helper?
- Should `secrets.py` move into a future `cloud_init/` package if cloud-init gets split?
- Should `validation.py` remain a permanent stable facade, or only a transitional aggregate for repository tests and callers?

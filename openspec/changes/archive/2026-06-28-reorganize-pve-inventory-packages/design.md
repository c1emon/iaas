## Context

`scripts/pve_inventory/` has grown from a compact inventory renderer into several overlapping concerns:

```text
scripts/pve_inventory/
├── cli.py / render.py / model.py / validation.py     inventory generation
├── cluster_validation.py / vm_validation.py          source validation
├── cloud_init.py / secrets.py                        cloud-init helpers
├── preflight.py / preflight_api.py / ...             online readiness checks
├── health.py                                        online current-state checks
└── pve_api/                                         shared API/runtime layer
```

The newly consolidated `pve_api/` layer gives online checks a cleaner boundary, but the surrounding modules are still flat. The next pressure point is discoverability: new PVE work has to ask whether a module is an entrypoint, a domain model, a validation helper, an online-check helper, or a transport adapter.

The root Makefile and PVE Makefile invoke stable module entrypoints (`python -m scripts.pve_inventory.cli`, `python -m scripts.pve_inventory.preflight`, `python -m scripts.pve_inventory.health`, and cloud-init helpers). Those should remain stable while internal helper modules move.

Desired shape:

```text
scripts/pve_inventory/
├── cli.py                    stable inventory CLI facade
├── preflight.py              stable online preflight CLI facade
├── health.py                 stable online health CLI facade
├── cloud_init.py             stable cloud-init CLI facade, unless later split safely
├── paths.py
├── pve_api/                  shared PVE API/runtime/errors/protocol
├── checks/
│   ├── results.py            shared CheckResult/reporting
│   ├── preflight/
│   │   ├── api.py            API-backed readiness checks + urllib transitional adapter
│   │   ├── model.py          derived readiness expectations
│   │   └── ssh.py            optional SSH adjunct checks
│   └── health/
│       └── core.py           health check internals, if split from facade
└── inventory/                optional later phase
    ├── model.py
    ├── render.py
    └── validation/
        ├── cluster.py
        ├── vm.py
        └── passthrough.py
```

## Goals / Non-Goals

**Goals:**

- Group online-check helper code under `scripts/pve_inventory/checks/`.
- Preserve stable operator-facing module entrypoints and Makefile behavior.
- Preserve public-ish test imports where they intentionally target facades (`preflight.py`, `health.py`, `cli.py`) while allowing internal helper imports to move.
- Make `pve_api/` remain the only PVE API/runtime adapter package.
- Keep the first implementation small enough to review as a refactor, not a behavior change.

**Non-Goals:**

- Do not change PVE health or preflight result IDs, severity semantics, exit behavior, or live access behavior.
- Do not combine preflight and health into a single command.
- Do not move PVE-domain code into `scripts/common/`.
- Do not redesign inventory generation or cloud-init behavior in the same step.
- Do not add new online checks, mutation operations, or runtime credentials.

## Decisions

### Decision: Start with online-check helpers, not the whole package

Move the preflight helper modules and shared check results first:

- `preflight_results.py` → `checks/results.py`
- `preflight_model.py` → `checks/preflight/model.py`
- `preflight_api.py` → `checks/preflight/api.py`
- `preflight_ssh.py` → `checks/preflight/ssh.py`

Rationale: these files already form a coherent online-check cluster and have the highest naming clutter. Moving them produces immediate readability gains without disturbing inventory rendering internals.

Alternative considered: move everything into `inventory/`, `checks/`, and `cloud_init/` in one change. Rejected because it increases import churn and makes behavior-preservation review harder.

### Decision: Keep top-level command facades stable

Keep `preflight.py`, `health.py`, `cli.py`, and `cloud_init.py` at top level unless a later step proves a facade split is valuable. These modules are the contract for `python -m` and Makefile usage.

Rationale: the repo already treats these module paths as command surfaces. Moving helper modules is low-risk; moving command modules risks unnecessary operator-facing churn.

Alternative considered: move command entrypoints into nested packages and add wrappers. Rejected for this change because wrapper modules can become another layer of thin compatibility code.

### Decision: Split `health.py` only if it remains mechanical

Health internals may move to `checks/health/core.py`, but only if the split is mostly import relocation and top-level `health.py` remains a small CLI/facade. If the split starts requiring broad rewrite, defer it.

Rationale: `health.py` is large enough to benefit from separation, but it is also newer and behavior-sensitive. The refactor should stay boring.

### Decision: Avoid compatibility shims for removed internal helper modules

Do not preserve top-level internal modules such as `preflight_api.py` as shims unless tests or external scripts demonstrate a real dependency.

Rationale: the previous `preflight_config.py` thin wrapper was removed because it obscured the real boundary. Internal helper shims recreate the same maintenance smell.

Alternative considered: leave shim modules for every moved file. Rejected unless a module is a documented command/import surface.

## Risks / Trade-offs

- Import churn hides a behavior change → Run focused online-check tests plus the full scripts test suite and `make check`.
- External local scripts import internal helper modules → Prefer stable facades for public imports; document moved internals through tests and source references.
- `health.py` split becomes too large → Defer health internals to a later task if it stops being mechanical.
- Circular imports through facades → Ensure moved helpers import shared low-level modules (`checks/results.py`, `pve_api/`, model/runtime) rather than top-level command modules.

## Migration Plan

1. Add `checks/` package skeletons.
2. Move shared check results and preflight helper modules into `checks/`.
3. Update `preflight.py`, `health.py`, tests, and internal imports.
4. Optionally split `health.py` internals into `checks/health/core.py` if straightforward.
5. Run focused PVE preflight/health/API/runtime tests.
6. Run `uv run pytest scripts/tests`, `make check`, and `openspec validate reorganize-pve-inventory-packages`.

Rollback is straightforward: restore the moved modules and imports. No infrastructure state, credentials, inventory output, or generated artifacts are changed by the refactor itself.

## Open Questions

- Should `health.py` internals move in the first implementation, or should the first pass only move preflight helpers and shared results?
- Should `cloud_init.py` eventually become a `cloud_init/` package, or is its current single-file CLI shape acceptable?
- Should inventory validation be split into `inventory/validation/` in a follow-up change after online-check package cleanup lands?

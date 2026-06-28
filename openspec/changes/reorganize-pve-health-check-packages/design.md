## Context

The PVE package now separates online preflight helpers under `checks/preflight/`, with shared result/reporting primitives in `checks/results.py`. Health checks still live mostly in the top-level `health.py` facade:

```text
scripts/pve_inventory/
├── health.py                    stable CLI/facade, but also owns internals
├── checks/
│   ├── results.py               shared CheckResult/reporting
│   ├── preflight/               organized preflight internals
│   └── health/                  currently only a package skeleton
└── pve_api/                     shared read-only API/runtime/error boundary
```

`health.py` contains several distinct responsibilities: runtime/facade handling, expectation derivation, API reachability/quorum checks, node capacity checks, storage checks, VM/template checks, HA checks, and Ceph checks. Keeping all of that in the facade makes future health work harder to review and increases the risk of accidentally mixing health current-state semantics with preflight readiness semantics.

This change should be deliberately narrower than a health rewrite. The goal is to move cohesive health internals into `checks/health/` while leaving `scripts.pve_inventory.health` as the stable command and import facade.

## Goals / Non-Goals

**Goals:**

- Move health current-state implementation helpers into `scripts/pve_inventory/checks/health/` modules.
- Preserve the stable top-level `scripts.pve_inventory.health` command facade, `python -m` behavior, and test-facing exports.
- Keep health semantics separate from preflight readiness semantics.
- Preserve health result IDs, severity policy, report output, runtime parsing, API redaction behavior, and exit behavior.
- Keep `pve_api/` as the shared read-only API/runtime/error/protocol boundary.

**Non-Goals:**

- Do not combine health and preflight commands or result semantics.
- Do not change thresholds or add/remove health checks unless implementation reveals a blocker that requires artifact updates first.
- Do not move `pve_api/`, offline inventory helpers, or cloud-init helpers.
- Do not introduce compatibility shims for old internal health helper modules; preserve only the documented top-level health facade.

## Decisions

### Decision: Keep `health.py` as a facade and move cohesive internals

Target shape:

```text
scripts/pve_inventory/checks/health/
├── __init__.py
├── model.py          HealthThresholds, HealthExpectations, derive_health_expectations
├── core.py           run_health_checks orchestration over API/client facts
├── node.py           quorum/node capacity/storage helpers, if split remains mechanical
├── vm.py             template and declared VM health helpers, if split remains mechanical
└── infra.py          HA/Ceph helpers, if split remains mechanical
```

`health.py` should keep command parsing, runtime loading facade exports, `run_health`, `main`, and `__all__`, delegating to `checks.health.*` for internals.

Rationale: the top-level module path is the stable operator/test-facing surface. Moving internals without moving the facade improves maintainability without changing commands.

Alternative considered: move the entire command to `checks/health/cli.py` and add a wrapper. Rejected because it creates compatibility code without adding value for operators.

### Decision: Split only where the move stays mechanical

Start with `checks/health/model.py` and `checks/health/core.py`. Split further into `node.py`, `vm.py`, or `infra.py` only if helper dependencies remain one-directional and do not create circular imports.

Rationale: `health.py` was previously identified as not a trivial split. A conservative first pass reduces churn and avoids designing a premature hierarchy.

Alternative considered: create many tiny modules immediately. Rejected because health helper functions share normalization, emit, and redaction utilities; over-splitting can increase coupling.

### Decision: Keep shared results and PVE API boundaries untouched

Health modules should import result primitives from `checks.results` and API types/errors from `pve_api`, not from the top-level `health.py` facade.

Rationale: internals depending on the facade would create circular imports and blur command-vs-implementation boundaries.

## Risks / Trade-offs

- Health result drift → Preserve existing result IDs/messages/severities and run focused `test_pve_health.py` plus API/runtime tests.
- Circular imports through the facade → Ensure `checks/health/*` modules never import `scripts.pve_inventory.health`.
- Over-splitting makes health harder to follow → Begin with `model.py` and `core.py`; only split node/vm/infra groups when dependencies stay simple.
- Runtime redaction changes accidentally → Keep `pve_api` redaction/error behavior as the single source and preserve existing tests.

## Migration Plan

1. Map all helpers and tests that depend on `scripts.pve_inventory.health` exports.
2. Move health expectation dataclasses and derivation into `checks/health/model.py` while re-exporting stable symbols from `health.py`.
3. Move health check orchestration/helper functions into `checks/health/core.py` and optionally node/vm/infra modules if mechanical.
4. Keep `health.py` as CLI/facade with unchanged `parse_args`, `run_health`, `main`, and `__all__` behavior.
5. Update internal tests only where they intentionally target moved internals; keep facade tests importing from `scripts.pve_inventory.health`.
6. Run focused health/preflight/API/runtime tests, full scripts tests, `make check`, and OpenSpec validation.

Rollback is straightforward: restore moved helpers into `health.py` and revert imports. No PVE state, credentials, generated artifacts, or live resources are changed by the refactor itself.

## Open Questions

- Should health internals stop at `model.py` + `core.py`, or is a node/vm/infra split worth the extra files after implementation mapping?
- Which health helper functions, if any, are intentionally test-facing beyond the top-level facade exports?
- Should repeated normalization helpers eventually become shared check utilities, or stay health-local to avoid premature generalization?

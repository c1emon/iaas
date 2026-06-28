## Context

The repository now has multiple Python inventory tools under `scripts/`:

- `scripts/pve_inventory/` owns PVE cluster and VM source-of-truth validation, rendering, generated-output checks, cloud-init helpers, and explicit online PVE operations.
- `scripts/services_inventory/` owns documentation-only service metadata validation and generated Markdown documentation.

Some helpers in `scripts/pve_inventory` are actually domain-neutral primitives: `ValidationError`, `require`, YAML/text I/O, basic schema assertions, and the CLI failure boundary pattern. `services_inventory` currently imports those helpers from `scripts.pve_inventory`, creating an implicit dependency on PVE internals.

The roadmap explicitly calls for Phase 4a to extract small Python common primitives while avoiding a broad `scripts/common/` framework. This change should make ownership clearer without changing validation semantics, generated artifacts, or offline/online boundaries.

## Goals / Non-Goals

**Goals:**

- Introduce an explicit `scripts/common/` package for domain-neutral Python primitives.
- Make both PVE and services inventory code depend on common primitives instead of using PVE inventory as the shared layer.
- Remove direct `scripts.services_inventory` imports from `scripts.pve_inventory.*` internals.
- Preserve current CLI contracts: expected validation failures exit `1`, use the `FAIL validation: ...` stderr prefix, and do not print Python tracebacks.
- Preserve generated outputs for unchanged source-of-truth files.
- Preserve default offline behavior; this refactor must not add PVE, OPNsense, switch, SSH, or secret dependencies to `make check`.

**Non-Goals:**

- Creating a generic inventory framework or domain service layer.
- Moving PVE cluster, VM, passthrough, cloud-init, preflight, health, or API client policy into common modules.
- Moving service metadata schema, warning, endpoint, exposure, auth, or rendering policy into common modules.
- Consolidating PVE runtime adapters or API clients; that belongs to a later optional roadmap phase.
- Changing root command names, CLI flags, output files, generated schemas, or validation rules.

## Decisions

### Decision: Use `scripts/common/` for primitives only

Create a small `scripts/common/` package with modules for narrow helper categories:

- `errors`: shared validation exception and assertion helper.
- `validation`: basic YAML/schema type and shape assertions.
- `io`: YAML/JSON/text file primitives and domain-neutral stale-file comparison helpers.
- `cli`: optional thin CLI validation boundary helper.
- `markdown`: optional Markdown table cell escaping primitive.

Rationale: a package boundary makes shared ownership explicit while keeping the surface small enough to review. The common layer must not import `scripts.pve_inventory` or `scripts.services_inventory`.

Alternative considered: leave helpers in `pve_inventory` and document that services may import them. Rejected because it preserves misleading ownership and makes future PVE refactors risky for service inventory.

Alternative considered: create a broad `scripts/common/inventory.py` or `scripts/common/render.py`. Rejected because it would invite domain policy and renderer orchestration into common code.

### Decision: Keep domain ordering and policy outside common I/O

Common I/O can compare expected file content with existing files and report missing/stale paths. PVE-specific generated-output ordering such as `tfvars`, `ansible`, `docs`, and `template_build_env` should remain in PVE code by passing ordered comparisons into the common primitive.

Rationale: the stale-output comparison mechanism is common, but which artifacts matter and in what order is domain behavior.

### Decision: Common validation remains primitive, not semantic

Move helpers that assert structural properties such as mapping/list/bool/positive-int/non-empty-string/unknown-keys. Keep helpers and constants that encode service names, endpoint choices, VM hostname rules, Ansible group rules, PVE tags, static IP logic, and PVE storage semantics in their owning domain modules.

Rationale: this preserves the roadmap rule that `scripts/common/` carries primitive helper code, not homelab or infrastructure policy.

### Decision: Preserve behavior with tests instead of changing contracts

The implementation should update tests around the new common helpers and keep existing behavior tests for PVE inventory, service inventory, CLI validation failures, Markdown escaping, and generated-output drift checks. Generated files should not change for unchanged YAML input.

Rationale: the value of this change is dependency hygiene. Any behavior drift should be treated as accidental unless explicitly documented in a later change.

## Risks / Trade-offs

- Common layer grows into a framework → Keep modules narrow, reject domain constants/policy, and review new common helpers against the primitive-only rule.
- Import churn causes accidental behavior changes → Move one helper category at a time and run existing tests plus generated-output checks.
- PVE generated-output mismatch order changes → Keep artifact ordering in PVE code rather than hiding it in common I/O.
- CLI failure formatting changes → Centralize only the thin boundary helper and retain tests for `FAIL validation: ...`, exit code `1`, and no traceback.
- Markdown escaping behavior changes → If extracted, keep the existing table-cell behavior byte-for-byte and verify generated service docs remain unchanged.

## Migration Plan

1. Add `scripts/common/` with primitive modules and tests where useful.
2. Move or copy primitive helpers into common modules.
3. Update PVE inventory code to import primitives from common while preserving its public validation/rendering entrypoints.
4. Update services inventory code to import primitives from common and remove all `scripts.pve_inventory.*` imports.
5. Keep or remove thin compatibility wrappers only if needed by internal imports; avoid treating wrappers as the long-term shared API.
6. Run offline validation and generated-output checks.

Rollback is straightforward: revert the import and helper relocation changes. No data migration or infrastructure state change is involved.

## Open Questions

- Should `scripts.pve_inventory.errors` and `scripts.pve_inventory.validation_common` remain as compatibility wrappers for one change cycle, or should all internal imports move directly to `scripts.common` immediately?
- Should Markdown table-cell escaping be extracted in this change, or deferred unless both inventory renderers need the same behavior?

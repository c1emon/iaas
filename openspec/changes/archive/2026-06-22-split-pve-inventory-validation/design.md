## Context

The PVE inventory generator currently exposes `validate_cluster()` and `validate_vms()` from `scripts/pve_inventory/validation.py`. That module also owns shared type/assertion helpers, URL/IP parsing utilities, cluster automation validation, VM resource/storage/boot normalization, and the main VM validation loop. Passthrough validation already lives in `scripts/pve_inventory/passthrough.py`, but it imports helper functions back from `validation.py`.

The next roadmap item is P0 reliability work: repeatable offline checks, generator check targets, CI validation, and later a separate read-only online preflight. A smaller validation module boundary now will make those additions easier without changing operator-facing behavior.

## Goals / Non-Goals

**Goals:**

- Split validation code into focused modules with clear ownership.
- Preserve the current `scripts.pve_inventory.validation` public import surface for callers and tests.
- Preserve current offline validation semantics, normalized dictionaries, and generated outputs.
- Avoid import cycles between passthrough validation and the validation façade.
- Keep the change small enough to verify with existing tests and generator check commands.

**Non-Goals:**

- No new YAML schema fields or inventory behavior.
- No online PVE API checks or preflight implementation.
- No migration of generated output paths or CLI flags.
- No conversion to dataclasses or a larger validation framework.
- No cleanup of unrelated renderer/model code.

## Decisions

1. Keep `validation.py` as a compatibility façade.
   - Decision: move implementation into new modules, then re-export the existing helper and entrypoint names from `validation.py`.
   - Rationale: existing tests and external scripts can continue importing `validate_cluster` and `validate_vms` from the old path.
   - Alternative considered: update every caller to new module paths and remove `validation.py`. Rejected because it creates needless churn for a behavior-preserving refactor.

2. Extract shared assertion helpers to `validation_common.py`.
   - Decision: move `as_mapping`, `as_list`, `require_positive_int`, `require_bool`, `require_non_empty_string`, `require_unknown_keys`, and `require_url_like` to a common module.
   - Rationale: passthrough, cluster validation, and VM validation all need these helpers. A common module prevents `passthrough.py` from importing through the façade.
   - Alternative considered: keep helpers in `validation.py`. Rejected because new implementation modules would depend on the façade and make cycles more likely.

3. Separate cluster and VM validation modules.
   - Decision: create `cluster_validation.py` for `validate_automation()` and `validate_cluster()`, and `vm_validation.py` for `parse_static_ip()`, VM resource/storage/boot normalization, and `validate_vms()`.
   - Rationale: cluster YAML and VM YAML are separate source-of-truth documents with separate validation concerns. This boundary aligns with the CLI flow and future check targets.
   - Alternative considered: one `validation/` package with multiple files. Rejected for now because a flat module split is enough and avoids package/file path migration complexity.

4. Preserve tests as compatibility tests.
   - Decision: do not change existing test imports unless a new targeted assertion is useful.
   - Rationale: keeping current imports proves the façade remains compatible while implementation moves underneath it.

## Risks / Trade-offs

- Import cycle introduced during extraction → Mitigation: make `validation_common.py` dependency-light and update `passthrough.py` to import helpers directly from it.
- Behavior drift from copy/move errors → Mitigation: run the focused PVE inventory pytest file and generator `--check` after the split.
- Error message changes break operator expectations or tests → Mitigation: preserve existing `require(...)` messages while moving functions.
- Too many tiny modules too early → Mitigation: split only along existing concerns: common, cluster, VM, passthrough.

## Migration Plan

1. Add `validation_common.py`, `cluster_validation.py`, and `vm_validation.py`.
2. Move existing logic without changing validation messages or normalized output shapes.
3. Replace `validation.py` with re-exports of the existing public names.
4. Update `passthrough.py` helper imports to use `validation_common.py`.
5. Run focused tests and the inventory check command.
6. Rollback is a normal git revert because there are no data migrations or generated format changes.

## Open Questions

- None for this change. Larger validation improvements, typed models, online PVE preflight, and root check targets should be handled by later OpenSpec changes.

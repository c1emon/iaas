## Context

`infra/tofu/modules/pve-cloudinit-vm/main.tf` contains two `proxmox_virtual_environment_vm` resources selected by complementary counts. Their VM arguments and nested blocks are currently identical. The protected resource alone declares literal `lifecycle.prevent_destroy = true`; OpenTofu lifecycle meta-arguments cannot be safely selected from an ordinary runtime variable, so the duplication is intentional.

The root offline gate already runs pytest, OpenTofu formatting, and OpenTofu validation. GitNexus identifies the HCL file but does not model its resource-body semantics, so source comparison is the appropriate evidence for this guard.

## Goals / Non-Goals

**Goals:**

- Detect any one-sided edit to common VM resource behavior before plan/apply.
- Encode a narrow, reviewable allowlist of the three intentional difference classes.
- Fail clearly when the guard cannot prove parity.
- Add no parser/runtime dependency and keep the guard within existing offline pytest.

**Non-Goals:**

- Do not merge the resources, generate HCL, change resource addresses, or move OpenTofu state.
- Do not prove provider behavior, plan equivalence, or live VM equivalence.
- Do not allow future resource differences merely because they appear inside `lifecycle`; new exceptions require a separate spec/design update.

## Decisions

### Preserve two resource blocks

Keep the current protected/unprotected resources and complementary `count` selection. The protected branch retains literal `prevent_destroy = true`; the unprotected branch omits it.

Alternative considered: one resource with conditional `prevent_destroy`. This is rejected because lifecycle protection is a static meta-argument boundary and the current split provides distinct protected/unprotected resource addresses and state-migration semantics.

Alternative considered: generate both resources from templates. This reduces visible duplication but introduces a code-generation layer for one module and makes reviewed HCL less direct.

### Use explicit source markers and exact normalization

Add stable comments immediately around each resource:

```text
# parity-guard: protected-begin
resource ...
# parity-guard: protected-end

# parity-guard: unprotected-begin
resource ...
# parity-guard: unprotected-end
```

A focused Python test should:

1. Require each marker exactly once and in the expected order.
2. Extract exactly one complete marked resource block for each branch.
3. Assert the expected resource labels and exact complementary count expressions.
4. Assert exactly one literal `prevent_destroy = true` in the protected block and none in the unprotected block.
5. Normalize the two resource headers and count lines to common placeholders and remove only the verified protected `prevent_destroy = true` line.
6. Normalize line endings and trailing whitespace, then compare all remaining text exactly.
7. Emit a unified diff and fail on any remaining difference.

This is deliberately stricter than semantic HCL equivalence: reordered attributes or branch-specific comments fail until both blocks are synchronized. That strictness keeps the implementation small and makes the duplicated text itself the reviewed invariant. Existing OpenTofu formatting/validation remains responsible for HCL syntax.

Alternative considered: add an HCL parser dependency and compare ASTs. It would tolerate harmless ordering changes but increases toolchain and normalization complexity for two adjacent, repository-formatted blocks. The marker-based exact comparison is sufficient and fail-closed here.

### Keep the allowlist literal and non-extensible at runtime

The guard may normalize only:

- `resource "proxmox_virtual_environment_vm" "protected"` versus `"unprotected"`;
- `count = local.vm_is_protected ? 1 : 0` versus `count = local.vm_is_protected ? 0 : 1`;
- the single protected-only `prevent_destroy = true` line.

It must not accept regex-configured ignored attributes, arbitrary lifecycle differences, or a repository variable that broadens exclusions. An intentional fourth difference requires review of the OpenSpec contract and guard code together.

### Run through existing pytest and aggregate validation

Place the focused test under `scripts/tests/` so normal pytest and `make check` execute it automatically. Do not create an online check or run plan/apply. Negative unit cases should exercise missing/duplicate markers, invalid selector/protection lines, and an unrelated body difference so the guard itself is proven fail-closed.

## Risks / Trade-offs

- [Harmless formatting or comment drift fails parity] → Keep both blocks formatted and synchronized; strict textual parity is intentional for maintainability.
- [Marker-based extraction does not parse HCL] → Require exact markers and selector/protection lines, compare all marked text, and retain `tofu fmt`/`tofu validate` as separate syntax gates.
- [A maintainer weakens normalization to land a one-sided change] → Encode only literal permitted transformations and require tests for rejected extra differences.
- [Future OpenTofu capabilities make duplication unnecessary] → Handle resource consolidation in a separate change with state and lifecycle migration analysis.

## Migration Plan

1. Add the explanatory comment and four exact parity markers without changing resource contents or addresses.
2. Add the normalization/comparison test and focused negative tests.
3. Run focused pytest, OpenTofu format/validation, and the root aggregate offline gate.

Rollback removes the markers/test and explanatory comment. No infrastructure rollback or state movement is needed because the implementation does not change resource behavior.

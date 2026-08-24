## Why

The PVE cloud-init VM module intentionally duplicates protected and unprotected resources because OpenTofu lifecycle protection must be a static resource-level declaration. Without an offline structural guard, a later VM argument, nested block, ignore rule, or precondition can be updated on only one branch and silently create lifecycle-dependent behavior drift.

## What Changes

- Keep the protected and unprotected `proxmox_virtual_environment_vm` resources separate; do not attempt to parameterize or merge lifecycle behavior.
- Add an explanatory source comment documenting why the duplication exists and which differences are intentional.
- Add a focused offline structural test that compares both resource bodies after normalizing only the resource label, complementary `count`, and protected-only literal `prevent_destroy = true` declaration.
- Require the guard to fail closed when either resource/marker is missing, duplicated, malformed, or differs outside the explicit allowlist.
- Report an actionable normalized diff when parity fails.
- Run the guard through the existing pytest/root `make check` path without provider credentials, PVE access, OpenTofu plan, or mutation.
- Do not rewrite HCL automatically, change resource addresses, move state, or alter current protected/unprotected behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pve-automation-foundation`: Adds an offline structural parity contract for the intentionally duplicated protected and unprotected VM resource definitions.

## Impact

- Affected areas:
  - Comments/guard markers in `infra/tofu/modules/pve-cloudinit-vm/main.tf`.
  - A focused structural test under `scripts/tests/`.
  - Existing root pytest and aggregate offline validation paths.
- Operational impact:
  - Future one-sided VM resource edits fail review/CI before plan or apply.
  - No current resource address, lifecycle setting, state, plan, or live VM changes.
- Dependencies:
  - Reuse Python standard-library text/diff utilities and existing OpenTofu formatting/validation gates; add no HCL parser dependency.

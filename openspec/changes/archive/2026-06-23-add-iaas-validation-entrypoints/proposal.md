## Why

The PVE automation foundation now has multiple useful validation and operation entrypoints, but they are not yet shaped as a small, predictable command surface that can be run consistently by an operator, a cloud CI job, or a future internal CI runner.

The roadmap calls for reliability work before adding more online automation. Operators need one offline validation path that can be trusted before running PVE preflight, plan, or apply-like workflows. CI also needs a safe first scope that validates and reports without requiring PVE, OPNsense, switch, 1Password, or high-privilege environment access.

## What Changes

- Standardize root-level validation commands for generation, stale generated output checks, Python tests, YAML linting, OpenTofu formatting, OpenTofu validation, and aggregate offline checks.
- Keep online PVE checks and mutation-capable operations outside the default offline `check` path.
- Add a CI-compatible command surface so local operators and CI run the same offline validation logic.
- Add cloud CI validation that runs offline checks only and never performs PVE, OPNsense, switch, OpenTofu apply, Packer build, or Ansible mutation.
- Document the distinction between offline validation, explicit online preflight/plan, and manual mutation workflows.

## Capabilities

### New Capabilities

- `iaas-validation-entrypoints`: Provide safe, repeatable local and CI validation entrypoints for the repository.

### Modified Capabilities

- None.

## Impact

- New OpenSpec capability:
  - `openspec/changes/add-iaas-validation-entrypoints/specs/iaas-validation-entrypoints/spec.md`
- Planned repository areas:
  - Root `Makefile` command surface.
  - CI workflow configuration, if cloud CI is enabled.
  - Documentation describing local vs CI vs online command boundaries.
- Operational impact:
  - Default checks remain offline and safe.
  - CI validates and reports only.
  - PVE online preflight and plan remain explicit operator actions.
  - Apply-like operations remain outside CI for this change.

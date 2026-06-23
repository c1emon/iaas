## Why

The first P0 validation change established a safe offline `make check`, but the remaining reliability work is still split across runbooks, ad-hoc operator knowledge, and deferred hygiene checks. Before adding online PVE preflight, planning, or internal CI triggers, operators need one clear P0 closure change that documents state/cache/secret handling and hardens offline validation without introducing live infrastructure access or mutation.

## What Changes

- Document PVE local state backup/restore, `.cache` handling, runtime secret injection, and generated-output sensitivity rules.
- Add an offline secret scanning path suitable for local operators and CI, with an explicit baseline/allowlist strategy if needed.
- Standardize explicit local hygiene targets that remain outside mutation paths, including Ansible syntax-check as an explicit target rather than a default gate requirement.
- Strengthen passthrough regression coverage for null/empty passthrough declarations, cloud-init/Ansible inventory edge cases, and generated OpenTofu dynamic block inputs.
- Keep all online checks, planning, guest SSH verification, internal CI trigger paths, and apply-like operations out of scope.

## Capabilities

### New Capabilities
- `pve-state-and-secret-operations`: Documents state, cache, runtime secret injection, and generated-output sensitivity expectations for PVE automation.

### Modified Capabilities
- `iaas-validation-entrypoints`: Adds P0 offline hygiene entrypoints such as secret scanning and explicit Ansible syntax-check while preserving the offline-safe default validation boundary.
- `pve-inventory-validation-structure`: Extends offline regression expectations for passthrough edge cases and generated output shape.

## Impact

- Affected areas:
  - Root `Makefile` validation/hygiene targets.
  - GitHub Actions offline validation workflow if secret scanning is promoted into CI.
  - PVE runbooks or documentation under `docs/`, `README.md`, and/or `infra/tofu/pve/README.md`.
  - PVE inventory tests under `scripts/tests/` and generator behavior checks if missing edge cases are found.
- Operational impact:
  - Default checks remain offline and safe.
  - Operators get clearer state/secret/cache rules before running online workflows.
  - CI remains validation/reporting only and does not gain infrastructure credentials.
- Non-goals:
  - PVE online preflight, OpenTofu plan, Ansible guest ping/verification, internal CI triggers, and any mutation-capable workflow.

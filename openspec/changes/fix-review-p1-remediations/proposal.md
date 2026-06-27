## Why

The June 2026 global code review identified a small set of P1 remediation items that should be fixed before larger validation, cloud-init checksum, or Python module consolidation work.

The highest-impact issue is a direct contract mismatch: generated guest cloud-init currently gives the `ops` automation user password-protected sudo, while guest verification treats `sudo -n true` as a hard readiness check. New VMs can therefore initialize successfully but fail repository-owned verification.

Other P1/P2 hygiene items also create avoidable operational noise: a broken legacy switch smoke script remains in `scripts/`, architecture documentation has drifted from inventory facts, local runtime artifacts need explicit tracked-file hygiene, validation CLIs can expose Python tracebacks for normal input errors, and malformed static IP values can surface as low-context parser exceptions.

## What Changes

- Align the guest automation access model by treating `ops` as the non-interactive automation user and preserving `sudo -n true` as a hard guest verification check.
- Keep `clemon` as the human administration user with password-protected sudo.
- Retire the broken legacy `scripts/sks8300_smoke.py` entrypoint instead of rebuilding the old smoke matrix in this change.
- Correct architecture documentation that conflicts with the current PVE inventory source of truth.
- Confirm and enforce repository hygiene for runtime artifacts such as `terraform.tfstate*`, `.terraform/`, `.venv/`, `.cache/`, `ansible/collections/`, and `.DS_Store` without deleting ignored local files automatically.
- Normalize validation CLI failures so expected inventory/config errors print stable operator-readable messages and exit with status 1 rather than showing Python tracebacks.
- Wrap invalid PVE VM `static_ip` parsing errors in repository validation errors with field context.

## Capabilities

### New Capabilities

- `iaas-repository-hygiene`: Defines expectations for retiring broken repository entrypoints and keeping human architecture documentation aligned with source-of-truth inventory facts.

### Modified Capabilities

- `pve-automation-foundation`: Updates the guest user and automation access model so `ops` supports non-interactive sudo for automation while `clemon` remains a human admin user.
- `pve-guest-verification`: Clarifies that non-interactive `ops` sudo is a hard check for reachable guests and must remain aligned with cloud-init user rendering.
- `iaas-validation-entrypoints`: Adds stable validation CLI error behavior and tracked runtime artifact hygiene to offline-safe checks.
- `pve-inventory-validation-structure`: Requires malformed static IP values to fail through contextual validation errors.
- `pve-state-and-secret-operations`: Clarifies local runtime state/cache hygiene and tracked-file expectations.

## Impact

- Affected areas:
  - `inventory/pve-cluster.yml` guest user sudo declarations.
  - `ansible/playbooks/pve/tasks/verify-guest.yml` semantics and related tests/docs if needed.
  - `scripts/sks8300_smoke.py` and any references to it.
  - `docs/architecture.md` PVE node facts.
  - `.gitignore`, docs, or offline hygiene checks for runtime artifacts as needed.
  - `scripts/pve_inventory/cli.py`, `scripts/services_inventory/cli.py`, and related tests.
  - `scripts/pve_inventory/vm_validation.py` invalid static IP handling and tests.
- Operational impact:
  - New guests rendered from inventory should pass the repository's `ops` non-interactive sudo verification when reachable and correctly initialized.
  - Operators get clearer validation failures for normal input mistakes.
  - Local ignored runtime artifacts are not automatically deleted by this change.
- Non-goals:
  - Do not add cloud-init manifest/checksum verification.
  - Do not broaden VM name, Ansible group, PVE tag, or services Markdown validation beyond the static IP error-context fix.
  - Do not add OPNsense vars schema validation.
  - Do not extract `scripts/common/` or consolidate PVE API/runtime layers.
  - Do not merge OpenTofu protected/unprotected VM resources.

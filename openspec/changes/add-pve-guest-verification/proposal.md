## Why

PVE online preflight now validates the host/control-plane side, but operators still need an explicit guest-side verification workflow after VMs are expected to exist. The current Ansible guest check is useful but fail-fast and not documented as a P1 operational visibility workflow with clear warn/skip behavior for offline guests.

## What Changes

- Add an explicit PVE guest verification capability for repo-managed VMs declared in `inventory/vms.yml` and rendered into the generated Ansible inventory.
- Make the canonical guest verification command repository-owned, for example `make pve-verify-guests`, while preserving existing PVE Ansible target compatibility where appropriate.
- Use Ansible as the primary implementation path and SSH as `ops` through the local SSH agent / 1Password SSH Agent; repository code SHALL NOT read or store private keys.
- Verify guest identity and readiness signals read-only: SSH reachability, hostname, declared static IP, qemu-guest-agent, `ops` passwordless sudo, root SSH disabled, and expected inventory groups/tags where available.
- Treat declared VMs that are powered off, unreachable, or otherwise not online as warnings rather than blocking failures in the first version.
- Treat DNS checks as warnings in the first version because DNS automation is not yet in scope.
- Keep guest verification outside default `make check` and GitHub Actions cloud CI; it remains an explicit online operation.
- Preserve plan/apply/destroy, guest configuration/repair, package installation, user creation, SSHD changes, DNS mutation, and firewall/switch changes as non-goals.

## Capabilities

### New Capabilities
- `pve-guest-verification`: Defines explicit read-only guest-side verification for repo-managed PVE VMs using generated Ansible inventory.

### Modified Capabilities
- `iaas-validation-entrypoints`: Records that PVE guest verification is an explicit online target outside default offline validation and cloud CI.

## Impact

- Affected areas:
  - Root `Makefile` and `infra/tofu/pve/Makefile` PVE target surface.
  - `ansible/playbooks/pve/verify-guests.yml` and any helper Ansible tasks needed to report warn/skip/pass/fail semantics.
  - Generated PVE Ansible inventory assumptions from `scripts/pve_inventory/` if additional non-secret host vars are required.
  - PVE/OpenTofu documentation and validation docs describing when to run guest verification.
  - Tests for generated inventory, command-surface boundaries, and offline-safe CI exclusion.
- Operational impact:
  - Operators get a post-provision guest visibility check without changing VMs.
  - Unreachable declared guests produce warnings in the first version, avoiding false blocking when VMs are intentionally stopped.
  - Default offline validation remains unchanged and safe for disconnected workstations and cloud CI.
- Non-goals:
  - Creating, starting, stopping, or modifying VMs; installing packages; changing users, sudoers, SSHD, DNS, firewall, switch, or PVE configuration; guest repair; or automatic CI execution with internal credentials.

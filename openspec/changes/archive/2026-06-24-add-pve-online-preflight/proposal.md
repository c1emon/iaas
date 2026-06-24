## Why

P0 made repository validation repeatable and safe offline, but operators still need an explicit online readiness check before running PVE plan/apply-like workflows. The current `pve-check-pve` target is a useful smoke check, but it is hard-coded and does not validate the declared API identity, template, VMID, PCI mapping, snippet, or wrapper readiness described by the repository source of truth.

## What Changes

- Add an explicit `make pve-preflight` entrypoint for read-only online PVE readiness checks.
- Prefer PVE API checks for resources exposed by the control plane: API authentication, expected nodes, bridges, storage, template VM records, VMID ownership, and PCI mappings.
- Allow SSH adjunct checks for node-local facts that are not reliably available through the API, such as installed host-side wrappers and sudo reachability.
- Derive expected resources from the validated PVE YAML model rather than hard-coded bridge/storage names.
- Report pass/warn/fail/skip results clearly, with blocking readiness issues causing a non-zero exit.
- Keep online preflight outside the default offline `make check` path and outside GitHub cloud CI.
- Preserve plan/apply/destroy, guest SSH verification, cloud-init snippet upload, Packer build, and infrastructure mutation as separate explicit workflows.

## Capabilities

### New Capabilities
- `pve-online-preflight`: Defines explicit read-only online PVE readiness checks, API-first behavior, SSH adjunct boundaries, and reporting semantics before plan/apply-like workflows.

### Modified Capabilities
- `iaas-validation-entrypoints`: Records that `pve-preflight` is an explicit online target and must remain outside default offline validation and cloud CI.

## Impact

- Affected areas:
  - Root `Makefile` and `infra/tofu/pve/Makefile` PVE target surface.
  - New PVE preflight command implementation, likely under `scripts/pve_inventory/` to reuse existing validated inventory/model code.
  - PVE/OpenTofu documentation and runbooks describing `op run --env-file infra/tofu/pve/.env.pve-opentofu.tpl -- make pve-preflight`.
  - Tests for preflight expected-resource derivation, result severity, and fake API/SSH client responses.
- Operational impact:
  - Operators get a safer explicit check before live plan/apply-like PVE workflows.
  - API credentials and optional SSH context are required only when the explicit online target is run.
  - Default offline validation remains unchanged and safe for disconnected workstations and cloud CI.
- Non-goals:
  - OpenTofu plan/apply/destroy, Packer build, cloud-init snippet upload, guest SSH verification, PVE role/ACL mutation, PCI mapping creation, and internal CI triggers.

## Why

The planned K3s application platform depends on external foundation services such as OPNsense, TrueNAS, internal DNS, sing-box, Harbor, and external databases. Those services currently exist as architecture knowledge, but they are not yet represented as recovery units that can be validated, health-checked, or used to reconcile storage-network facts before K3s work begins.

This change establishes the first foundation recovery control surface without deploying K3s, changing live services, or automating service lifecycle operations.

## What Changes

- Add an operator-authored foundation recovery inventory for cluster-external foundation hosts and services.
- Model foundation services as recovery units with runtime, host, dependencies, restore order, health checks, backup/restore metadata, break-glass access, and known-risk markers.
- Add a generated documentation view of the foundation recovery inventory.
- Add offline validation for the inventory schema, dependency references, restore-order consistency, and non-sensitive generated output.
- Add explicit online foundation health checks for service-level HTTP/TCP/DNS/API reachability.
- Add storage-network fact validation that reconciles the documented storage VLAN/subnet and the nodes expected to access storage-backed K3s volumes.
- Keep foundation checks read-only and explicit; this change does not deploy, upgrade, restart, reconfigure, or restore foundation services.

## Capabilities

### New Capabilities

- `foundation-recovery-checks`: Defines the foundation recovery inventory, generated recovery documentation, read-only health checks, and storage-network fact validation needed before K3s platform PoCs.

### Modified Capabilities

- None.

## Impact

- Planned repository areas:
  - new foundation inventory under `inventory/`
  - generated foundation recovery documentation under `docs/generated/`
  - foundation inventory validation and rendering code under `scripts/`
  - explicit Make targets for offline validation/generation and online health checks
  - documentation updates that link the new recovery inventory and checks
- Explicit non-impact:
  - No K3s cluster creation or Kubernetes manifests.
  - No mutation of OPNsense, TrueNAS, DNS, Harbor, Authentik, sing-box, databases, switches, PVE, or Docker hosts.
  - No secret values committed to the repository; inventory may reference 1Password or other secret references only.
  - No application deployment, upgrade, migration, restore, or decommission automation.

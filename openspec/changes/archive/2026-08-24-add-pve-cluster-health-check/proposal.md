## Why

P1 is moving the repository from VM creation toward safe operation of a small PVE environment. The existing `pve-preflight` command checks whether declared resources are ready before plan/apply-like VM workflows, but operators also need a separate day-to-day and maintenance-precheck view of cluster health.

Cluster health is a different question from apply readiness: it should answer whether the PVE cluster is currently quorate when applicable, required nodes are online, required datastores are active and not critically full, referenced templates still exist, and declared long-lived VMs appear to be present and running.

## What Changes

- Add an explicit `make pve-health` entrypoint for read-only online PVE cluster health checks.
- Implement the health command as a new PVE online operation, likely under `scripts/pve_inventory/health.py`, backed by a reusable Python PVE API layer that uses `proxmoxer` while exposing only read-only health/query methods to callers.
- Check API reachability, cluster quorum when exposed, required and optional node status, node capacity thresholds, required datastore presence/activity/usage, referenced template status, declared VM runtime status, HA status when available, and Ceph health when available.
- Treat declared-but-unused placeholder nodes as warnings rather than failures.
- Warn when declared long-lived VMs are missing or stopped; do not warn for missing/stopped ephemeral lab VMs.
- Keep HA and Ceph endpoint absence as skipped, not failed, unless the endpoint returns actionable unhealthy state.
- Keep `pve-health` outside default `make check` and outside cloud CI.
- Preserve all maintenance, reboot, migration, update, apply, destroy, and remediation actions as non-goals.

## Capabilities

### New Capabilities
- `pve-cluster-health-check`: Defines explicit read-only PVE cluster health checks, capacity thresholds, VM/template runtime status semantics, HA/Ceph skip behavior, and reporting/exit rules.

### Modified Capabilities
- `iaas-validation-entrypoints`: Records that `pve-health` is an explicit online target and must remain outside default offline validation and cloud CI.

## Impact

- Affected areas:
  - Root `Makefile` and `infra/tofu/pve/Makefile` PVE target surface.
  - New PVE health command implementation under the PVE inventory/online operations code.
  - Python dependency metadata for the `proxmoxer` PVE API SDK.
  - Tests using fake PVE API responses for quorum, nodes, capacity, storage, templates, VMs, HA, and Ceph behavior.
  - Documentation explaining `make pve-health` and how it differs from `make pve-preflight`.
- Operational impact:
  - Operators get a safe read-only health report before maintenance or routine review.
  - Runtime PVE API credentials are required only when the explicit health target is run.
  - Default offline validation remains unchanged and safe for disconnected workstations and cloud CI.
- Non-goals:
  - VM migration, node maintenance mode, node reboot, package updates, PVE upgrades, Ceph mutation such as `noout`, notification delivery, automatic remediation, and inclusion in default offline checks or cloud CI.

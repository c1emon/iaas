## Why

P1 prioritizes moving from VM creation toward safe operation of a small PVE environment. After service metadata and cluster health checks, operators need a documented procedure for planned PVE node maintenance such as reboot-only maintenance or package update followed by reboot.

This repository should not jump straight to automated maintenance playbooks. Rolling maintenance can affect quorum, storage, VM availability, passthrough workloads, and guest reachability. The first step should be a runbook with explicit precheck/postcheck gates, manual decision points, single-node handling, and clear abort criteria.

## What Changes

- Add a PVE rolling maintenance runbook at `docs/runbooks/pve-rolling-maintenance.md`.
- Define safe boundaries for reboot-only and package-update maintenance.
- Require `make pve-health` as the main precheck, per-node continue gate, and post-maintenance health gate.
- Recommend `make pve-verify-guests` before/after maintenance to capture guest runtime baseline and outcome.
- Distinguish multi-node rolling maintenance from single-node maintenance where downtime may be unavoidable.
- Document per-node operator flow: choose node, inspect VMs, decide migrate/shutdown/defer, perform manual maintenance, wait for node return, run health checks, then decide whether to continue.
- Document VM handling policy for long-lived, ephemeral lab, and passthrough VMs.
- Document Ceph handling as conditional/future only; do not automate or require Ceph operations in non-Ceph environments.
- Define abort and continue criteria.
- Keep this change docs-only: no playbooks, scripts, Make targets, migrations, reboots, updates, or notifications.

## Capabilities

### New Capabilities
- `pve-rolling-maintenance-runbook`: Defines the documented manual procedure, safety gates, single-node branch, VM handling policy, Ceph caution, and abort/continue criteria for PVE rolling maintenance.

### Modified Capabilities
- `iaas-validation-entrypoints`: Records that maintenance remains explicit and outside default offline validation and cloud CI.

## Impact

- Affected areas:
  - New runbook under `docs/runbooks/`.
  - Documentation references to `make pve-health`, `make pve-preflight`, and `make pve-verify-guests` as distinct gates.
  - OpenSpec requirements for maintenance boundaries.
- Operational impact:
  - Operators gain a repeatable manual maintenance procedure before any future automation.
  - The runbook reduces risk by making prechecks, per-node checks, guest checks, and abort rules explicit.
  - No live infrastructure behavior changes.
- Non-goals:
  - Automated VM migration, node maintenance mode, node reboot, package update, PVE upgrade, Ceph `noout`, notification delivery, internal CI triggers, or automatic remediation.

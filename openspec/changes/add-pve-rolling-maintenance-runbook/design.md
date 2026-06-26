## Context

The roadmap recommends PVE operations runbooks/playbooks after the earlier safety rails are stable. The current P1 ordering makes the dependencies explicit:

```text
add-service-metadata-inventory
        │
        ▼
add-pve-cluster-health-check
        │
        ▼
add-pve-rolling-maintenance-runbook
        │
        ▼
future: maintenance playbook / notifications / internal CI triggers
```

The rolling maintenance runbook should use `pve-health` as the main gate. It may reference `pve-preflight` when VM lifecycle planning is relevant and `pve-verify-guests` for guest-side verification, but it must not automate maintenance actions in this first version.

## Goals / Non-Goals

**Goals:**

- Add a PVE rolling maintenance runbook for planned reboot-only and package-update maintenance.
- Keep the first version documentation-only.
- Include pre-maintenance checks, per-node procedure, post-node verification, post-maintenance verification, abort criteria, and recordkeeping guidance.
- Cover both multi-node rolling maintenance and single-node maintenance where downtime may be unavoidable.
- Make `make pve-health` the required health gate before maintenance, after each node, and after the full maintenance window.
- Recommend `make pve-verify-guests` to capture guest baseline and post-maintenance guest state.
- Document VM handling policy for long-lived, ephemeral lab, and passthrough VMs.
- Document Ceph handling only as conditional/future guidance.

**Non-Goals:**

- Do not add an Ansible playbook or script for maintenance.
- Do not add a Make target for maintenance orchestration.
- Do not migrate, stop, start, reboot, or otherwise change VMs automatically.
- Do not enter or leave PVE node maintenance mode automatically.
- Do not run `apt update`, `apt full-upgrade`, `reboot`, or PVE package operations automatically.
- Do not mutate Ceph state such as `noout`.
- Do not add notifications.
- Do not add internal CI triggers.
- Do not place maintenance behavior in `make check` or cloud CI.

## Decisions

### Start with a runbook, not automation

Rolling maintenance affects availability and can require context-specific operator decisions. The first version should therefore be a runbook, not a playbook. Automation can be introduced later only after the manual process is reviewed and repeated successfully.

The runbook may include command examples for manual execution, such as PVE health checks, guest verification, PVE package review/update, migration examples, and reboot examples. These examples must be clearly marked as operator-run commands, not repository automation.

### Separate single-node and multi-node flows

Small homelab environments may be effectively single-node, even if the inventory contains placeholder nodes. The runbook should not pretend a single-node environment can perform no-downtime rolling maintenance.

The runbook should branch early:

```text
single-node maintenance:
  accept planned downtime
  review/stop guests manually when needed
  maintain the node
  verify node and guests after return

multi-node rolling maintenance:
  maintain one node at a time
  preserve quorum
  migrate or shut down workloads by operator decision
  verify after each node before continuing
```

### Use explicit gates

The runbook should use these gates:

```text
before maintenance:
  make pve-health must have no FAIL
  WARN conditions must be reviewed and accepted or resolved
  optional make pve-verify-guests baseline recorded

after each node:
  node is reachable through PVE UI/API
  make pve-health has no FAIL
  WARN conditions are reviewed before continuing

after full maintenance:
  make pve-health has no FAIL
  make pve-verify-guests is run or consciously skipped with reason
```

`pve-preflight` remains distinct: it is an apply-readiness gate, not a routine maintenance gate. It should be used if the operator plans VM lifecycle changes during or after maintenance.

### Define VM handling policy

For each VM on the target node, the runbook should guide the operator to classify and choose a handling strategy:

```text
long_lived, no passthrough:
  candidate for migration or controlled shutdown depending on cluster capacity and service tolerance

long_lived, passthrough:
  generally not live-migratable; plan shutdown/downtime or defer maintenance

ephemeral_lab:
  may remain stopped; do not destroy/recreate unless a separate reviewed workflow scopes it
```

The runbook may show example PVE CLI commands, such as `qm migrate <vmid> <target-node>` or `qm shutdown <vmid>`, but the repository must not execute them automatically.

### Document package update and reboot as manual operations

The runbook should cover two maintenance types:

```text
reboot-only:
  health -> workload handling -> reboot -> health -> guest verification

package-update-and-reboot:
  health -> review package plan -> workload handling -> manual package update -> reboot if needed -> health -> guest verification
```

Package commands may be included as examples, but operators should review PVE official documentation, repository/channel configuration, and package plan output before proceeding.

### Keep Ceph conditional and non-mutating

Ceph is not currently a repository requirement. The runbook should include a conditional section:

```text
if Ceph is not configured:
  skip Ceph handling

if Ceph is configured in the future:
  require Ceph health review before maintenance
  consider noout only as an explicit manual operator decision
  do not automate Ceph flag changes in this repository yet
```

### Define abort and continue criteria

The runbook should tell operators when to stop rather than continue to the next node.

Abort examples:

- `make pve-health` reports any FAIL after a node returns.
- Quorum is lost or unstable.
- A required datastore is inactive or unavailable.
- A long-lived VM is unexpectedly missing.
- Guest verification reports new hard failures.
- The node does not return within the operator's expected timeout.
- PVE UI/API becomes unavailable.
- Unexplained VM or storage locks remain.

Continue examples:

- The target node is back online.
- `make pve-health` has no FAIL.
- WARN conditions are reviewed and accepted.
- Expected VMs are running, migrated, or intentionally stopped.
- The operator records the outcome before choosing the next node.

## Risks / Trade-offs

- A runbook is less convenient than automation → This is intentional for the first version; maintenance automation should follow repeated successful manual practice.
- Command examples can be mistaken for automatic repository behavior → Mark all mutation examples as manual operator commands.
- Single-node environments cannot be truly rolling → Include a separate single-node branch and require planned downtime acceptance.
- Ceph guidance can be dangerous if too specific → Keep Ceph handling conditional and non-mutating.
- VM migration semantics depend on storage, passthrough, and cluster configuration → Present migration as an operator decision, not an automatic rule.

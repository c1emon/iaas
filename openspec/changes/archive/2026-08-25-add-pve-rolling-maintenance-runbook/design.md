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

- Add a PVE rolling maintenance runbook for planned reboot-only and package-update maintenance, with reboot treated as a separate planned or package-required action.
- Keep the first version documentation-only.
- Include pre-maintenance checks, per-node procedure, post-node verification, post-maintenance verification, abort criteria, and recordkeeping guidance.
- Cover both multi-node rolling maintenance and single-node maintenance where downtime may be unavoidable.
- Require recovery evidence, an explicit maintenance deadline, and alternate console access before disruptive work.
- Treat live quorum, workload-placement capacity, storage compatibility, and passthrough constraints as eligibility checks for a rolling flow rather than inferring eligibility from declared node count.
- Make `make pve-health` the required health gate before maintenance, after each node, and after the full maintenance window.
- Recommend `make pve-verify-guests` to capture guest baseline and post-maintenance guest state.
- Document VM handling policy for long-lived, ephemeral lab, and passthrough VMs.
- Keep Ceph maintenance out of scope unless the environment already has a separately reviewed procedure.

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

The runbook may include command examples for manual execution, such as PVE health checks, guest verification, package-plan review, migration, and reboot. Mutation examples must be clearly marked as operator-run, version-sensitive commands, must not be combined into an unattended copy/paste sequence, and must direct the operator to the applicable PVE documentation before execution.

Alternative considered: add a repository-owned maintenance wrapper that sequences these commands. This is rejected because it would blur the manual approval boundary before the procedure has operational evidence.

### Separate single-node and multi-node flows

Small homelab environments may be effectively single-node, even if the inventory contains placeholder nodes. Conversely, multiple declared or online nodes do not prove that workloads can be evacuated safely. The runbook should not pretend either case provides no-downtime rolling maintenance.

The runbook should branch early:

```text
single-node maintenance:
  accept planned downtime
  confirm working local or out-of-band console access
  review/stop guests manually when needed
  maintain the node
  verify node and guests after return

multi-node rolling maintenance:
  confirm live quorum and supported cluster topology
  confirm target workloads fit on compatible nodes and storage
  maintain one node at a time
  preserve quorum
  migrate or shut down workloads by operator decision
  verify after each node before continuing
```

If quorum cannot be observed, evacuation capacity or storage compatibility is uncertain, or a required passthrough workload has no accepted downtime plan, the runbook should classify the rolling path as blocked. A declared inventory count is not sufficient evidence.

Alternative considered: use `inventory/pve-cluster.yml` node count to choose the branch automatically. This is rejected because inventory can contain unavailable placeholder nodes and does not prove live capacity or storage compatibility.

### Use explicit gates

The runbook should use these gates:

```text
before maintenance:
  make pve-health must have no FAIL
  WARN conditions must be reviewed and accepted or resolved
  recovery evidence, console access, scope, and stop deadline are recorded
  clustered flow has explicit quorum evidence; SKIP is not sufficient
  optional make pve-verify-guests baseline recorded

after each node:
  node is reachable through PVE UI/API
  make pve-health has no FAIL
  WARN conditions are reviewed before continuing

after full maintenance:
  make pve-health has no FAIL
  make pve-verify-guests is compared with baseline or consciously skipped with reason
```

`pve-preflight` remains distinct: it is an apply-readiness gate, not a routine maintenance gate. It should be used if the operator plans VM lifecycle changes during or after maintenance.

`pve-health` is necessary but not sufficient for maintenance admission. It does not prove recoverability, console access, evacuation capacity, storage compatibility, or that a skipped quorum check is safe. Those items remain explicit operator gates in the runbook.

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

package-update:
  health -> review package plan -> workload handling -> manual package update -> reboot only if planned or required -> health -> guest verification
```

Package commands may be included as version-sensitive manual examples, but operators must review the applicable PVE documentation, repository/channel configuration, package plan output, and recovery posture before proceeding. The runbook must not imply that every package update requires a reboot or that an update is reversible by a generic package rollback.

### Keep Ceph conditional and non-mutating

Ceph is not currently a repository requirement. The runbook should include a conditional section:

```text
if Ceph is not configured:
  skip Ceph handling

if Ceph is configured:
  require an environment-specific reviewed Ceph maintenance procedure
  defer this runbook when that procedure is absent
  do not prescribe or automate Ceph flag changes here
```

Alternative considered: include generic `noout` guidance. This is rejected because flag selection and cleanup depend on the Ceph topology and maintenance window; incomplete generic guidance can leave the cluster in a degraded operating posture.

### Define abort and continue criteria

The runbook should tell operators when to stop rather than continue to the next node.

Abort examples:

- `make pve-health` reports any FAIL after a node returns.
- Quorum is lost or unstable.
- A required datastore is inactive or unavailable.
- A long-lived VM is unexpectedly missing.
- Guest verification reports new hard failures.
- The node does not return by the recorded stop deadline.
- PVE UI/API becomes unavailable.
- Unexplained VM or storage locks remain.

Continue examples:

- The target node is back online.
- `make pve-health` has no FAIL.
- WARN conditions are reviewed and accepted.
- Expected VMs are running, migrated, or intentionally stopped.
- The operator records the outcome before choosing the next node.

Recovery guidance should stop the sequence, preserve health output and operator notes, use the preselected console/recovery path, and require a fresh admission decision before resuming. It must not recommend automatic unlock, package rollback, VM restart, or Ceph flag mutation as a generic first response.

## Risks / Trade-offs

- A runbook is less convenient than automation → This is intentional for the first version; maintenance automation should follow repeated successful manual practice.
- Command examples can be mistaken for automatic repository behavior → Mark all mutation examples as manual operator commands.
- Version-sensitive PVE package or migration syntax can become stale → Keep examples bounded, require applicable official documentation review, and avoid unattended command chains.
- Single-node environments cannot be truly rolling → Include a separate single-node branch and require planned downtime acceptance.
- Health success can be mistaken for complete maintenance readiness → State that recovery, console, capacity, storage, and quorum evidence are separate admission gates.
- Ceph guidance can be dangerous if generic → Defer to a separately reviewed environment-specific procedure and provide no generic flag recipe.
- VM migration semantics depend on storage, passthrough, and cluster configuration → Present migration as an operator decision, not an automatic rule.

## Migration Plan

1. Add and link the documentation-only runbook without changing any executable target.
2. Validate the runbook against the health and guest-verification contracts and confirm no offline or CI path invokes maintenance.
3. Trial the runbook through tabletop review before using it for a live window; live execution evidence belongs to a later operational record, not to this change's completion claim.

Rollback is documentation-only: revert the runbook and its references if the procedure is found unsafe. Reverting documentation cannot reverse maintenance actions already performed manually.

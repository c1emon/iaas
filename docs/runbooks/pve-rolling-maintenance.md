# PVE Rolling Maintenance

Use this runbook for planned PVE node reboot-only or package-update
maintenance. It is an operator procedure, not repository automation: this
repository does not migrate or stop VMs, update packages, reboot nodes, change
Ceph flags, or send notifications from this document.

Run online commands from the repository root with the required explicit runtime
context. For example, PVE API checks normally need the PVE 1Password
environment described in [the root operator guide](../../README.md). Do not add
these commands to `make check`, cloud CI, or an unattended command sequence.

## Admission record and prechecks

Before changing a node, record the following in the maintenance ticket or
operator log:

| Record | Required evidence |
| --- | --- |
| Scope | Reboot-only or package-update, target node(s), maintenance deadline, and operator |
| Recovery | Current backup/recovery evidence and a tested local, IPMI, or other out-of-band console path |
| Workloads | VM inventory for every target node, service tolerance, planned migration/shutdown/defer decision, and passthrough constraints |
| Cluster eligibility | For a rolling flow: live quorum evidence, compatible evacuation capacity, and storage compatibility |
| Warnings and outcome | Accepted warnings, commands actually run, per-node outcome, and follow-up actions |

Run the main health gate before starting:

```bash
# Online, read-only. Run manually with the required PVE runtime context.
make pve-health
```

Do not begin normal planned maintenance when it reports `FAIL`. Review every
`WARN`; resolve it or record why it is accepted for this window. When guest SSH
context is available, capture a baseline as well:

```bash
# Online, read-only; optional only when guest SSH context is available.
make pve-verify-guests
```

`make pve-preflight` is an apply-readiness check for VM lifecycle work. It is
not a routine maintenance gate. Run it only when a separately approved VM
lifecycle change is planned during or after this window.
It does not prove evacuation capacity, target-node storage compatibility, or
passthrough migratability. The command contracts and their runtime prerequisites
are documented in [the PVE automation guide](../../environments/astra/opentofu/pve/README.md).

Choose the flow from observed live conditions, not from the declared inventory
node count:

- **Single-node maintenance:** accept planned workload downtime and confirm a
  working local or out-of-band console before disruption. This is not
  no-downtime rolling maintenance.
- **Multi-node rolling maintenance:** proceed only when live quorum is
  reported as `PASS` by `make pve-health`, the target node is independently
  confirmed online, workloads can fit on compatible remaining nodes and storage, and
  each passthrough workload has an accepted downtime plan. A skipped or
  unverified quorum check is not evidence. If any of these facts is uncertain,
  stop and use the single-node/downtime plan or defer the window.

If Ceph is not configured, no Ceph step is required. Confirm this from the
environment; do not interpret a `SKIP ceph` result as proof that Ceph is absent,
because unavailable API data or insufficient permission can also be skipped. If
Ceph is configured or cannot be confirmed absent, this runbook requires a
separately reviewed, environment-specific Ceph maintenance procedure. Defer the
window if that procedure is absent; do not use generic `noout` or other Ceph
flag commands from this runbook.

## Handle workloads manually

For every VM on the target node, choose and record one of these actions before
touching the node:

| Workload | Operator decision |
| --- | --- |
| Long-lived VM without passthrough | Migrate, perform a controlled shutdown, or defer based on capacity and service tolerance. |
| Long-lived VM with passthrough or another non-migratable constraint | Usually plan downtime/controlled shutdown, or defer. Do not assume live migration is suitable. |
| Ephemeral lab VM | It may remain stopped or be handled manually. Do not destroy or recreate it implicitly. |

The following are version- and environment-sensitive **manual examples only**.
Review the applicable PVE documentation and actual workload state before each
one; do not copy them as an unattended chain:

```bash
# Inspect a selected node and its VMs.
pvesh get /nodes/<node>/qemu

# Manually migrate or stop one already-reviewed VM when the recorded plan says so.
qm migrate <vmid> <target-node>
qm shutdown <vmid>
```

## Maintain one node at a time

For each target node, complete this sequence and record the result before
selecting another node:

1. Reconfirm the target node, workload decisions, console path, and deadline.
   For a rolling flow, reconfirm quorum and remaining placement capacity.
2. Complete the recorded manual VM handling. Do not enter node maintenance
   mode, migrate, or stop a VM merely because this runbook lists an example.
3. Select exactly one maintenance type:
   - **Reboot-only:** perform the planned manual reboot, then wait for the node
     to return through the PVE UI/API and the selected console path.
   - **Package-update:** manually review the enabled PVE repository/channel and
     package plan first. Apply only the reviewed package update. Reboot only
     when it was planned or the reviewed update requires it; do not assume every
     update requires a reboot or has a generic package rollback.
4. After the node returns, run `make pve-health`. Do not continue if it reports
   `FAIL`; review and record every `WARN` before continuing.
5. Confirm every expected VM is running, migrated, or intentionally stopped;
   then record node-return time, health result, warnings, commands run, and any
   follow-up.

Migration or intentional shutdown can cause `make pve-health` to report a VM
missing from its declared inventory node. Treat that as an expected, explicitly
recorded maintenance deviation only while the VM handling decision remains in
effect. Before closing the window, restore the declared placement or record and
review any intentional longer-lived placement change; never silently treat the
warning as a healthy steady state.

## Stop, recover, or continue

Stop the sequence before another node if any of the following occurs:

- `make pve-health` reports `FAIL` after a node returns;
- quorum is lost, unstable, or cannot be verified for a clustered flow;
- required storage is inactive or unavailable;
- a long-lived VM is unexpectedly missing, new guest verification failures
  appear, or unexplained VM/storage locks remain;
- the node misses its recorded return deadline; or
- PVE UI/API is unavailable.

On a stop, preserve health output, relevant PVE task output, VM state, and the
maintenance record. Use the preselected console/recovery path. Do not begin
with automatic unlocks, VM restarts, package rollback, or Ceph flag mutation;
make a fresh admission decision before resuming.

Continue only when the maintained node is back online, `make pve-health` has no
failures, warnings are reviewed, expected VM state is understood, and the
outcome is recorded.

## Close the window

After all intended nodes are maintained, or after the window is stopped, run
the final online read-only health gate:

```bash
make pve-health
```

Compare a final `make pve-verify-guests` result with the baseline when guest
SSH context is available. A baseline that has no declared guests, unavailable
guest SSH, or `SKIP`/`WARN` output is an unavailable or limited baseline, not a
passing guest-verification result; record that limitation and do not use it to
claim guest health. If final guest verification is skipped, record the reason.
Close the record with the date, operators, node scope, reboot/package scope,
accepted warnings, commands run, health and guest-verification results,
recovery actions, and follow-ups.

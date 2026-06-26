## 1. Runbook Scope and Safety Boundaries

- [ ] 1.1 Confirm the first version is docs-only and does not add playbooks, scripts, Make targets, or mutation commands.
- [ ] 1.2 Define reboot-only and package-update-and-reboot as the documented maintenance types.
- [ ] 1.3 Document that all VM migration, shutdown, package update, reboot, node maintenance mode, and Ceph operations are manual operator actions.
- [ ] 1.4 Document that maintenance remains outside `make check`, GitHub cloud CI, and automatic internal CI triggers.

## 2. Precheck and Gate Design

- [ ] 2.1 Add a pre-maintenance checklist requiring `make pve-health` with no FAIL before normal planned maintenance.
- [ ] 2.2 Document that `pve-health` WARN conditions must be reviewed and accepted or resolved before continuing.
- [ ] 2.3 Recommend `make pve-verify-guests` as a guest baseline before maintenance when guest SSH context is available.
- [ ] 2.4 Document when `make pve-preflight` is relevant and when it is not part of routine maintenance.
- [ ] 2.5 Include operator context checks such as maintenance window, PVE UI/API access, console/out-of-band access, backups/snapshots confidence, and target node order.

## 3. Maintenance Flow Documentation

- [ ] 3.1 Document a single-node maintenance branch that explicitly accepts planned downtime.
- [ ] 3.2 Document a multi-node rolling maintenance branch that maintains one node at a time and preserves quorum.
- [ ] 3.3 Document per-node steps: select target node, inspect workloads, decide VM handling, perform manual maintenance, wait for node return, run health gate, and record outcome.
- [ ] 3.4 Include manual command examples for common operator actions where useful, clearly marked as manual and not repository automation.
- [ ] 3.5 Document post-node continue criteria before moving to the next node.
- [ ] 3.6 Document post-maintenance verification using `make pve-health` and recommended `make pve-verify-guests`.

## 4. VM, Storage, and Ceph Policy

- [ ] 4.1 Document VM handling policy for long-lived VMs without passthrough.
- [ ] 4.2 Document VM handling policy for long-lived passthrough VMs as usually non-live-migratable and downtime/defer candidates.
- [ ] 4.3 Document VM handling policy for ephemeral lab VMs and prohibit implicit destroy/recreate behavior in this runbook.
- [ ] 4.4 Document required storage and quorum concerns before and after node maintenance.
- [ ] 4.5 Add conditional Ceph guidance: skip when absent, review health when present, and keep `noout` or other Ceph mutations as explicit manual future/operator decisions.

## 5. Abort, Recovery, and Recordkeeping

- [ ] 5.1 Define abort criteria for post-node failures, lost quorum, datastore unavailability, guest verification failures, missing long-lived VMs, node return timeout, PVE API/UI outage, and unexplained locks.
- [ ] 5.2 Define continue criteria requiring node return, no `pve-health` FAIL, reviewed WARNs, expected VM state, and recorded outcome.
- [ ] 5.3 Document recovery posture: stop, preserve logs/state, avoid corrective automation first, and use existing state/cache/secret runbook guidance where relevant.
- [ ] 5.4 Add a maintenance record template for date, operator, nodes, package/reboot scope, warnings accepted, commands run, and follow-ups.

## 6. Validation

- [ ] 6.1 Run `openspec validate add-pve-rolling-maintenance-runbook`.
- [ ] 6.2 Review the runbook for consistency with `add-pve-cluster-health-check` and existing PVE safety boundaries.
- [ ] 6.3 Run `make check` if implementation only adds documentation and OpenSpec artifacts.
- [ ] 6.4 Confirm no default validation, cloud CI, or mutation workflow invokes maintenance behavior.

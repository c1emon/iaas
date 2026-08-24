## 1. Runbook Scope and Safety Boundaries

- [x] 1.1 Confirm the first version is docs-only and does not add playbooks, scripts, Make targets, or executable mutation entrypoints; clearly label any manual command examples.
- [x] 1.2 Define reboot-only and package-update as the documented maintenance types, with reboot performed only when planned or required.
- [x] 1.3 Document that all VM migration, shutdown, package update, reboot, node maintenance mode, and Ceph operations are manual operator actions.
- [x] 1.4 Document that maintenance remains outside `make check`, GitHub cloud CI, and automatic internal CI triggers.

## 2. Precheck and Gate Design

- [x] 2.1 Add a pre-maintenance checklist requiring `make pve-health` with no FAIL before normal planned maintenance.
- [x] 2.2 Document that `pve-health` WARN conditions must be reviewed and accepted or resolved before continuing.
- [x] 2.3 Recommend `make pve-verify-guests` as a guest baseline before maintenance when guest SSH context is available.
- [x] 2.4 Document when `make pve-preflight` is relevant and when it is not part of routine maintenance.
- [x] 2.5 Require a recorded maintenance scope and stop deadline, applicable backup/recovery evidence, and working local or out-of-band console access before disruptive work.
- [x] 2.6 Require explicit quorum evidence for clustered maintenance and manual evacuation-capacity, storage-compatibility, and passthrough checks before selecting the rolling branch.

## 3. Maintenance Flow Documentation

- [x] 3.1 Document a single-node maintenance branch that explicitly accepts planned downtime.
- [x] 3.2 Document a multi-node rolling maintenance branch that maintains one node at a time, preserves observable quorum, and blocks when workload placement is uncertain.
- [x] 3.3 Document per-node steps: select target node, inspect workloads, decide VM handling, perform manual maintenance, wait for node return, run health gate, and record outcome.
- [x] 3.4 Include manual command examples for common operator actions where useful, clearly marked as manual and not repository automation.
- [x] 3.5 Document post-node continue criteria before moving to the next node.
- [x] 3.6 Document post-maintenance verification using `make pve-health` and recommended `make pve-verify-guests`.

## 4. VM, Storage, and Ceph Policy

- [x] 4.1 Document VM handling policy for long-lived VMs without passthrough.
- [x] 4.2 Document VM handling policy for long-lived passthrough VMs as usually non-live-migratable and downtime/defer candidates.
- [x] 4.3 Document VM handling policy for ephemeral lab VMs and prohibit implicit destroy/recreate behavior in this runbook.
- [x] 4.4 Document required storage and quorum concerns before and after node maintenance.
- [x] 4.5 Add conditional Ceph guidance: skip when absent and defer this runbook when Ceph is present without a separately reviewed environment-specific maintenance procedure; do not prescribe Ceph flag mutations here.

## 5. Abort, Recovery, and Recordkeeping

- [x] 5.1 Define abort criteria for post-node failures, lost quorum, datastore unavailability, guest verification failures, missing long-lived VMs, node return timeout, PVE API/UI outage, and unexplained locks.
- [x] 5.2 Define continue criteria requiring node return, no `pve-health` FAIL, reviewed WARNs, expected VM state, and recorded outcome.
- [x] 5.3 Document recovery posture: stop, preserve logs/state, use the preselected console/recovery path, avoid generic corrective automation, and require fresh admission before resuming.
- [x] 5.4 Add a maintenance record template for date, operator, nodes, package/reboot scope, warnings accepted, commands run, and follow-ups.

## 6. Validation

- [x] 6.1 Run `openspec validate add-pve-rolling-maintenance-runbook`.
- [x] 6.2 Review the runbook for consistency with `add-pve-cluster-health-check` and existing PVE safety boundaries.
- [x] 6.3 Run `make check` if implementation only adds documentation and OpenSpec artifacts.
- [x] 6.4 Confirm no default validation, cloud CI, or mutation workflow invokes maintenance behavior.

# Roadmap and backlog

This is the current roadmap and backlog index for this repository. It summarizes
planning status without replacing detailed OpenSpec history, runbooks, or older
research notes.

This page is documentation-only. It does not archive, retask, or edit existing
OpenSpec changes, and it does not implement any roadmap item.

## Status source and precedence

When roadmap notes disagree, use this order to determine current status:

1. OpenSpec archived/active status and task completion.
2. Current repository behavior and documented command surface.
3. This roadmap summary.
4. Historical roadmap, remediation, or research prose.

Older documents may still say an item is "next" or "future" after the work has
been completed, archived, deferred, or superseded. Treat those notes as decision
context unless this page or OpenSpec says otherwise.

## Status categories

| Status | Meaning |
|---|---|
| Done | Implemented and, where applicable, archived in OpenSpec. |
| Complete pending archive | Implementation appears complete, but the active OpenSpec change has not been archived. |
| In progress | Active OpenSpec work exists and is not complete. |
| Planned | Near-term backlog item suitable for a focused future OpenSpec change. |
| Deferred | Scale-triggered or intentionally postponed; revisit only when the condition is met. |
| Superseded | Older wording or proposal seed has been replaced by later implementation, archive state, or current design. |

## Current priorities

- Keep repository checks offline and safe by default; online operations should
  remain explicit operator actions.
- Finish or archive completed OpenSpec changes before starting broad new roadmap
  work, so the active change list stays useful.
- Continue small, focused OpenSpec changes for infrastructure behavior; do not
  combine unrelated PVE, OPNsense, switch, and documentation changes.
- Preserve the current YAML source-of-truth model until scale or multi-operator
  workflow justifies a stronger inventory system.

## Complete pending archive

These active changes appear implementation-complete and should be verified and
archived separately. This roadmap intentionally does not edit their tasks or
archive state.

| Change | Outcome area |
|---|---|
| `manage-opnsense-filter-rules` | OPNsense filter rule management. |
| `support-opnsense-filter-rule-net-arrays` | OPNsense network-array support for filter rules. |
| `support-opnsense-filter-rule-port-arrays` | OPNsense port-array support for filter rules. |
| `refine-opnsense-filter-rule-identity-input` | OPNsense filter rule identity input refinement. |
| `manage-opnsense-pbr-gateways` | OPNsense policy-based routing gateway management. |
| `make-opnsense-filter-rule-inverts-optional` | Optional invert flags for OPNsense filter rules. |
| `make-opnsense-filter-rule-ports-optional` | Optional port fields for OPNsense filter rules. |
| `support-sks8300-interface-vlan-resources` | SKS8300 interface/VLAN resource support. |
| `add-pve-cluster-health-check` | PVE cluster health-check workflow. |

## Completed work

Completed work is summarized by outcome. Detailed task history remains in the
archived OpenSpec changes.

| Outcome | Representative references |
|---|---|
| PVE automation foundation, inventory validation, validation entrypoints, and reliability milestone. | `openspec/changes/archive/2026-06-22-add-pve-automation-foundation/`, `openspec/changes/archive/2026-06-22-split-pve-inventory-validation/`, `openspec/changes/archive/2026-06-23-add-iaas-validation-entrypoints/`, `openspec/changes/archive/2026-06-23-complete-p0-iaas-reliability/` |
| PVE online safety rails and runtime verification. | `openspec/changes/archive/2026-06-24-add-pve-online-preflight/`, `openspec/changes/archive/2026-06-26-add-pve-guest-verification/` |
| PVE rolling maintenance procedure. | [`docs/operations/03-pve.md`](operations/03-pve.md), `openspec/changes/archive/2026-08-25-add-pve-rolling-maintenance-runbook/` |
| PVE protected/unprotected VM resource parity guard. | `openspec/changes/archive/2026-08-25-guard-pve-cloudinit-vm-resource-parity/`, `tests/python/test_pve_cloudinit_vm_resource_parity.py` |
| OPNsense desired-state validation admission gate. | `openspec/changes/archive/2026-08-25-validate-opnsense-mutation-inputs/`, `make opnsense-validate` |
| PVE implementation/package maintenance and adapter consolidation. | `openspec/changes/archive/2026-06-28-consolidate-pve-api-runtime-adapters/`, `openspec/changes/archive/2026-06-28-reorganize-pve-health-check-packages/`, `openspec/changes/archive/2026-06-28-reorganize-pve-inventory-packages/`, `openspec/changes/archive/2026-06-28-reorganize-pve-cloud-init-packages/`, `openspec/changes/archive/2026-06-28-extract-python-common-primitives/` |
| Operator documentation reorganization. | `openspec/changes/archive/2026-06-30-reorganize-operator-documentation/`, [root operator manual](../README.md) |
| Roadmap consolidation. | `openspec/changes/archive/2026-06-30-consolidate-documentation-roadmaps/`, [current roadmap](roadmap.md) |
| Review remediation phases 1, 2, 3a, and 4a. | [historical remediation roadmap](review-remediation-roadmap.md) |
| OPNsense alias/VIP configuration and export support. | Archived OpenSpec history under `openspec/changes/archive/`. |
| Switch/SKS8300 automation migration and read-only export workflow. | Archived OpenSpec history under `openspec/changes/archive/`. |

## Planned backlog

These items are suitable for future focused changes. They are not implemented by
this roadmap consolidation.

| Item | Source / reason |
|---|---|
| OpenSpec archive cleanup | Several complete active changes should be verified and archived to reduce planning drift. |
| Documentation cleanup | Keep `docs/README.md`, this roadmap, and historical labels aligned; avoid treating old proposal queues as current status. |
| Architecture TODO consolidation | `docs/architecture.md` still tracks service placement, DNS/domain, monitoring, backup, and switch/management-port TODOs. Summarize or split them into focused docs when they become implementation work. |
| Service metadata and exposure details | Continue improving service metadata and generated docs before coupling DNS, reverse proxy, or firewall mutation. |

## Deferred / scale-triggered ideas

| Idea | Revisit when |
|---|---|
| NetBox / DCIM-IPAM source of truth | VLAN, IP, device, or multi-operator complexity outgrows YAML. |
| Terragrunt | OpenTofu roots/environments multiply enough that backend/provider duplication becomes painful. |
| Remote OpenTofu state | Multi-operator workflow or real CI apply requires shared state. |
| SOPS/age or similar secret workflow | Secret rotation/sharing needs exceed current 1Password/env injection practices. |
| GitOps auto-apply | A separate application platform exists and automatic mutation is safe; keep PVE, firewall, and switch apply manual for now. |
| Internal CI trigger path | Internal Forgejo/Woodpecker-style triggers are needed for read-only environment checks or release validation. |
| Lightweight notification helper | Long-running maintenance workflows need operator summaries or failure alerts. |
| High-privilege PVE hardware mapping bootstrap | PCI mapping management becomes frequent enough to justify a separate privileged OpenTofu root. |
| PVE API/runtime adapter consolidation beyond current state | New maintenance pain appears after the archived adapter consolidation and package reorganizations. |
| Deeper switch, DNS, firewall, or OPNsense mutation | Read-only export/diff and generated plan documentation exist first. |

## Superseded notes

- The proposal queue in
  [IaaS automation roadmap research](decisions/iaas-automation-roadmap-research.md)
  lists several items as next priorities that later moved to archived or active
  OpenSpec changes. Use OpenSpec state and this page for current status.
- The completed phases in
  [review remediation roadmap](review-remediation-roadmap.md) are retained for
  audit context; their unchecked later phases are backlog candidates, not a live
  sprint plan.

## Historical roadmap references

- [Review remediation roadmap](review-remediation-roadmap.md) — historical
  remediation plan with remaining backlog candidates.
- [IaaS automation roadmap research](decisions/iaas-automation-roadmap-research.md)
  — historical research snapshot and decision context.
- [Architecture notes](architecture.md) — current architecture inventory with
  documentation TODOs that may feed future backlog items.
- `openspec/changes/archive/` — archived implementation history and detailed
  task records.

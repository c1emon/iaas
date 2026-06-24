## Context

P0 established a safe offline validation boundary: `make check` and GitHub Actions validate generated outputs, tests, YAML, OpenTofu formatting/validation, and secret scanning without infrastructure credentials. P1 starts the transition from repository health to operational readiness for a small PVE environment.

The current online PVE check is `make pve-check-pve`, which delegates to `infra/tofu/pve/Makefile` and runs a hard-coded SSH command checking `br_dev`, `br_prod`, `images`, and `memory` on one host. That check is useful as a smoke test but does not derive expectations from `inventory/pve-cluster.yml` / `inventory/vms.yml`, does not validate the OpenTofu API identity, and does not detect template, VMID, PCI mapping, or host-wrapper readiness issues before a live plan/apply-like workflow.

The PVE automation stack already has the right source-of-truth boundary:

```text
inventory/pve-cluster.yml + inventory/vms.yml
        │
        ▼
scripts.pve_inventory validation/model
        │
        ├── generated.auto.tfvars.json ──▶ OpenTofu VM lifecycle
        ├── generated Ansible inventory ─▶ guest verification later
        └── generated docs/env artifacts
```

The preflight should reuse that validated model and compare it to live PVE state through read-only checks.

## Goals / Non-Goals

**Goals:**

- Add canonical root `make pve-preflight` as the explicit P1 online readiness command.
- Prefer PVE API checks for PVE control-plane resources used by OpenTofu.
- Allow SSH adjunct checks for node-local wrapper/sudo facts that the API cannot reliably prove.
- Derive expected resources from validated YAML/model data, not hard-coded strings.
- Distinguish required used resources from declared-but-unused placeholder resources.
- Produce a clear pass/warn/fail/skip report and non-zero exit for blocking readiness failures.
- Keep preflight outside `make check` and outside cloud CI.

**Non-Goals:**

- Do not run `tofu plan`, `tofu apply`, `tofu destroy`, or any provider planning/mutation.
- Do not upload, modify, or delete cloud-init snippets.
- Do not create, clone, start, stop, or modify VMs.
- Do not create or modify PVE roles, ACLs, users, API tokens, PCI mappings, storage, or bridges.
- Do not run guest SSH verification or Ansible guest checks; those belong to `add-pve-guest-verification`.
- Do not add GitHub Actions secrets or automatic credentialed CI.
- Do not turn this into a full PVE cluster health or maintenance framework.

## Decisions

### Use API-first checks with SSH adjuncts

`pve-preflight` should use PVE API checks for resources exposed by the control plane: authentication, nodes, bridges, storage, templates, VM records, and PCI mappings where available. This aligns the preflight with the OpenTofu provider identity and future internal CI usage.

SSH is allowed as an adjunct for host-local facts that are not reliably available through the API, such as `/usr/local/sbin/astra-pve-snippet-upload`, `/usr/local/sbin/astra-pve-template-build`, and passwordless sudo reachability for wrapper help/verification commands. SSH checks must remain read-only and must be skipped or reported separately when `PVE_HOST` / `PVE_SSH_USER` are not supplied.

Alternative considered: make the first preflight SSH-only because the current `pve-check-pve` is SSH-based. Rejected because the most important readiness path is whether the same API identity used by OpenTofu can see required resources.

### Derive an expected-resource graph from the validated PVE model

The preflight should not duplicate YAML parsing rules or parse HCL. It should reuse `validate_cluster`, `validate_vms`, and `build_model` to derive expected resources:

```text
required nodes       = VM nodes + template nodes referenced by VMs
required bridges     = VM network bridges on each VM node
required storage     = VM disk storage + cloud-init snippet storage + template storage roles
required templates   = VM template VMID/name/node records
required VMIDs       = declared VM IDs and expected ownership
required mappings    = passthrough mappings used by declared VMs on selected nodes
optional resources   = declared but currently unused nodes/mapping-node combinations
```

Used resources are blocking when missing or mismatched. Declared but unused placeholder resources should warn rather than fail in the first version, which preserves the current `node3` placeholder pattern.

### Keep `pve-preflight` separate from default offline validation

The root `make check` target remains offline and credential-free. `make pve-preflight` is explicit and should normally be invoked with runtime secrets, for example:

```bash
op run --env-file infra/tofu/pve/.env.pve-opentofu.tpl -- make pve-preflight
```

When SSH adjunct checks are desired:

```bash
op run --env-file infra/tofu/pve/.env.pve-opentofu.tpl -- \
  make pve-preflight PVE_HOST=cohe PVE_SSH_USER=pve-ops
```

The existing `pve-check-pve` target can become a compatibility alias to `pve-preflight` or remain as a legacy target, but documentation should identify `pve-preflight` as canonical.

### Report status using pass/warn/fail/skip semantics

The preflight report should be operator-readable and stable enough for later CI consumption. The initial human report should include check IDs or names, severity, and short context. Optional JSON output is desirable if it can be added without widening scope.

Suggested semantics:

```text
FAIL  blocking readiness issue; command exits non-zero
WARN  suspicious or placeholder condition; command exits zero if no failures
SKIP  optional section not run because optional context was absent
PASS  expected condition satisfied
```

Examples:

- API auth failure: fail.
- VM-used node missing: fail.
- Declared unused placeholder node missing: warn.
- SSH wrapper checks absent because no SSH context was provided: skip or warn, but not fail unless SSH checks are explicitly required.
- Wrapper missing when SSH checks are requested: fail.

### Keep VM ownership checks conservative

For each declared VMID, preflight should pass if the VMID is free. If it already exists, preflight should only pass when it appears to be owned by this repository, for example by matching expected VM name and repository-generated ownership markers such as `managed-by-opentofu` tags or `Managed by OpenTofu for <cluster>` description. An occupied VMID with an unexpected name or missing ownership marker should fail.

This avoids blocking repeat preflight after successful provisioning while still protecting against accidental takeover of unrelated VMs.

## Risks / Trade-offs

- PVE API endpoint coverage differs from expectations → Keep the implementation API-first but allow read-only SSH fallback for specific facts; document any endpoint limitations discovered during implementation.
- Preflight becomes too broad and drifts into mutation workflow → Enforce non-goals in specs and tests; no plan/apply/upload/create commands belong in this change.
- Placeholder nodes such as `node3` create false failures → Treat used resources as required and declared-unused resources as warnings for this first version.
- VM ownership heuristics may be imperfect → Use conservative fail behavior for mismatches and document the ownership markers used.
- SSH adjunct checks add credential complexity → Make API checks primary and report SSH checks separately; do not require SSH unless an operator explicitly provides that context or a later design promotes it.
- Sensitive runtime env values could leak in logs → Redact secrets and avoid printing token values or resolved `op run` values.

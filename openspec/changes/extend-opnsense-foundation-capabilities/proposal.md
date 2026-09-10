## Why

Repository-wide and independent multi-agent audits found failures in existing PVE,
K3s, network activation, recovery metadata and runtime entrypoint workflows. These
must be repaired and regression-tested before extending OPNsense. This proposal now
covers that prerequisite repair phase as well as the original feature scope; its
change ID is retained for continuity.

The generic runtime already manages static aliases, optional next-hop gateways and
API-backed filter rules, but its local alias admission gate rejects URL tables and
network groups supported by the pinned Collection. Existing read-only exports show
configuration, not a complete view of loaded alias tables, matching rule logs and
connection states. Callers need these basic capabilities without application-specific
routing assumptions.

## What Changes

- Repair existing runtime workflows first: explicit Make ordering and paths, source-bound cloud-init artifacts, authoritative storage resolution, operation-aware K3s admission and upgrade verification, correct handoff TLS identity, recoverable OPNsense activation, accurate validation, reviewable switch plans and target-attributed exports.
- Remove application policy from generic foundation inputs; validate dependency/recovery order and make health observations accurate and bounded. Preserve legacy inputs through an explicit compatibility path.
- Require a completed repair regression gate before the dependency refresh and all URL-table, network-group and diagnostic feature work. See `repair-plan.md` for audit coverage and acceptance boundaries.
- Refresh the Ansible execution stack to the reviewed 14.4.0/core 2.21.4 pair and align explicitly installed shared Collections; keep oxlorg.opnsense at stable 26.1.11. See `dependency-review.md`.

- Extend managed aliases with `urltable`, explicit refresh frequency and `networkgroup` references; preserve existing `host`, `network` and `port` behavior.
- Validate alias dependencies locally where provable, resolve external references through an explicit read-only preflight, and apply dependencies in a deterministic order.
- Add bounded, on-demand read-only diagnostics for alias loading, rule logs and connection states, with protected optional detail output and explicit unsupported/error results.
- Reuse existing Gateway and PBR workflows and document how callers supply ordinary aliases, next hops and rule fields. Preserve non-default gateway ownership, managed-rule identity and additive updates.
- Keep list providers, topology, addresses, application names, route preferences and failure policies entirely caller-owned.

## Capabilities

### New Capabilities
- `opnsense-readonly-diagnostics`: Explicit, bounded online inspection of loaded aliases, rule logs and connection states.

### Modified Capabilities
- `pve-automation-foundation`: Ordered execution, current-input artifact verification and authoritative snippet storage paths.
- `k3s-automation-operations`: Lifecycle-aware admission, truthful live facts, staged upgrades and observed-version verification.
- `platform-gitops-handoff`: Correct DNS/IP TLS identity and IPv6 connection handling.
- `foundation-recovery-checks`: Dependency-consistent recovery, optional neutral storage facts and trustworthy bounded health probes.
- `xikeos-network-resources-primary`: Reviewable, protected switch plan output.
- `opnsense-config-export`: Target-isolated exports with device attribution.
- `opnsense-pbr-gateway-management`: Explicit retry of configuration activation.
- `opnsense-filter-rule-management`: Explicit activation retry and inversion-aware rule validation.
- `opnsense-vip-management`: Explicit retry of configuration activation.
- `oci-runtime-delivery`: Repair arbitrary-directory entrypoints, align CI with the shipped baseline, gate features on repairs and preserve dependency/source layering.
- `opnsense-alias-management`: URL-table and network-group management, dependency ordering and external reference preflight.
- `opnsense-mutation-input-validation`: Correct existing Gateway/PBR admission before adding type-specific alias fields and dependency checks.

## Impact

Implementation spans the existing PVE and K3s orchestration, shared validators,
foundation model/probes, switch and OPNsense playbooks, Make/runtime entrypoints,
CI, representative synthetic tests and operator documentation, followed by the
small read-only diagnostic adapter and alias extensions. Repairs and the dependency
refresh precede feature code in separate focused commits. Reuse existing components
and the pinned `oxlorg.opnsense` dependency; do not create a workflow framework.

Gateway/PBR field shapes, ownership and credential boundaries remain unchanged;
incorrect numeric/inversion validation and activation recovery are explicitly repaired.
The neutral foundation schema is versioned and legacy migration is documented. This
change does not manage default routes, legacy rules, DNAT, applications, list hosting,
packet capture, state deletion or autonomous remediation. Live appliance qualification
and image publication are separate authorized operations, not this proposal's acceptance.

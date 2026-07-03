## Context

The K3s application platform design keeps several foundation services outside the cluster: OPNsense, TrueNAS, internal DNS, sing-box, Harbor, external databases, and Authentik. These services are required to recover the future application platform, but today their recovery metadata lives mostly in prose under `docs/architecture.md` and `docs/k3s-foundation-platform-design.md`.

The repository already has patterns for operator-authored YAML inventories, Python validation/rendering, generated Markdown docs, Make targets, and explicit online operations. This change applies those patterns to foundation recovery without creating K3s resources or mutating live services.

## Goals / Non-Goals

**Goals:**

- Add `inventory/foundation.yml` as the first operator-authored foundation recovery inventory.
- Model foundation hosts and services as recovery units, not application deployment targets.
- Generate a committed foundation recovery reference under `docs/generated/`.
- Provide offline schema/dependency/staleness checks that are safe in CI and disconnected workstations.
- Provide explicit online, read-only service health checks for foundation services.
- Reconcile storage-network facts that block K3s storage PoCs, especially storage VLAN/subnet and VM-only K3s storage access.

**Non-Goals:**

- Do not install or configure K3s, Cilium, Gateway API, Flux, TrueNAS CSI, or democratic-csi.
- Do not deploy, restart, upgrade, restore, or decommission foundation services.
- Do not mutate OPNsense, TrueNAS, DNS, Harbor, Authentik, sing-box, database, switch, PVE, Docker, or systemd state.
- Do not introduce new secrets management; use reference-only fields for 1Password or other external secret material.
- Do not replace the existing `inventory/services.yml` application service metadata model.

## Decisions

### Use a separate foundation inventory

Create a new inventory, tentatively `inventory/foundation.yml`, instead of expanding `inventory/services.yml`.

`inventory/services.yml` is documentation-only metadata for application endpoints owned by PVE VMs. Foundation recovery needs different semantics: restore order, required-before-K3s flags, break-glass access, backup/restore metadata, and storage-network facts. Keeping the inventories separate avoids overloading application service metadata with recovery-control concepts.

### Keep the first inventory recovery-focused

The first schema should cover:

```text
foundation_hosts
foundation_services
storage_networks
k3s_storage_access
```

Service records should include host, runtime, tier, dependencies, recovery order, whether the service is required before K3s recovery, health checks, backup profile, restore runbook reference, break-glass metadata, configuration source, and known risks.

This intentionally stops short of full lifecycle automation fields such as deploy steps, upgrade plans, rollback commands, drift remediation, and scheduler placement.

### Generate documentation from the inventory

Generate `docs/generated/foundation-recovery.md` from the inventory. The generated document should summarize the minimum startup set, recovery order, foundation host/service table, dependency table, health checks, backup/restore metadata, break-glass notes, storage-network facts, and warnings.

Generated output must remain non-sensitive. Secret values must never be rendered; secret references may be rendered if they are explicit reference strings rather than credential material.

### Split offline validation from online health checks

Offline validation should be safe for CI and local disconnected use:

```text
make foundation-generate
make foundation-check
```

Online health checks should be explicit and read-only:

```text
make foundation-health
```

Offline checks validate YAML shape, references, restore-order consistency, duplicate names, missing restore metadata, stale generated docs, non-sensitive generated output, and storage-network fact consistency. Online checks perform only service-level HTTP/TCP/DNS/API probes declared in the inventory.

### Keep online probes simple in the first version

The first online health checks should support service-level probes such as:

- TCP port reachable;
- HTTPS/HTTP endpoint reachable with an expected status range;
- DNS query returns an expected record or any valid answer;
- optional API health endpoint status for Harbor-like services.

They should not perform authenticated workflows, UI login, image pulls, database writes, proxy traffic mutation, firewall writes, or restore tests.

### Treat storage-network facts as preflight facts, not network automation

The storage-network section should reconcile documented facts needed before K3s storage PoCs:

- storage VLAN ID and expected subnet;
- TrueNAS storage endpoint;
- which hosts or future K3s node classes are expected to have storage access;
- the decision that only VM-based K3s nodes should access the storage VLAN in the first phase.

The implementation should validate internal consistency but must not configure VLANs, switch ports, OPNsense interfaces, or host networking.

## Risks / Trade-offs

- **Risk: inventory becomes stale.** Mitigation: generated documentation staleness check and explicit validation target.
- **Risk: operators put secrets in inventory.** Mitigation: validation and generated-output checks should reject obvious secret-like fields and document reference-only secret handling.
- **Risk: health checks are mistaken for full recovery testing.** Mitigation: label them as read-only service-level checks; keep quarterly restore drills as a separate documented requirement.
- **Risk: storage-network validation gives false confidence.** Mitigation: scope it to fact consistency only; it does not prove VLAN reachability or CSI readiness.
- **Risk: N100 remains a single point of failure.** Mitigation: record it as a known risk but do not try to remediate in this change.
- **Risk: online checks accidentally mutate infrastructure.** Mitigation: limit probes to GET-like HTTP, TCP connect, DNS query, and read-only status APIs.

## Migration Plan

1. Add the foundation inventory with current known services and storage facts from existing docs.
2. Add validation/rendering code and tests.
3. Add generated foundation recovery documentation.
4. Add Make targets for offline generate/check and explicit online health checks.
5. Update docs to point to the generated recovery reference and the design document.

Rollback is straightforward: remove the new inventory, generated document, scripts, targets, and documentation links. No live infrastructure state is changed.

## Open Questions

- What exact FQDNs should each health check use when multiple management/app addresses exist?
- Should health checks require an explicit environment flag in addition to a dedicated Make target?
- Should the first implementation check only presence of backup/restore metadata, or also validate timestamps from an external backup system later?

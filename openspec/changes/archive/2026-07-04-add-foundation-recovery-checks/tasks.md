## 1. Inventory Model

- [x] 1.1 Add `inventory/foundation.yml` with current foundation hosts, services, recovery order, dependencies, health checks, backup/restore metadata, break-glass metadata, known risks, and storage-network facts.
- [x] 1.2 Represent required-before-K3s services in the agreed recovery order: OPNsense, TrueNAS, internal DNS, sing-box, Harbor, external databases.
- [x] 1.3 Record Authentik as a foundation service with independent recovery and break-glass metadata, but not as a K3s recovery prerequisite.
- [x] 1.4 Record N100 as a known single point of failure without remediating it in this change.
- [x] 1.5 Record storage-network facts, including storage VLAN/subnet, TrueNAS storage endpoint, and VM-only K3s storage access scope.

## 2. Validation and Rendering Implementation

- [x] 2.1 Add a foundation inventory Python package or module under `scripts/` following existing repository validation/rendering patterns.
- [x] 2.2 Implement inventory loading and schema validation for hosts, services, dependencies, health checks, backup/restore metadata, break-glass metadata, known risks, and storage-network facts.
- [x] 2.3 Implement validation for duplicate names, unknown host references, unknown dependency references, missing restore order for required startup services, duplicate restore-order values, and missing critical-service health/restore metadata.
- [x] 2.4 Implement non-sensitive content checks that reject or flag obvious decrypted secret material while allowing external secret references.
- [x] 2.5 Implement generated Markdown rendering for `docs/generated/foundation-recovery.md`.
- [x] 2.6 Implement generated-output check mode that fails when the committed generated foundation recovery document is stale.
- [x] 2.7 Implement storage-network fact validation without contacting or mutating network infrastructure.

## 3. Explicit Online Health Checks

- [x] 3.1 Implement explicit read-only online foundation health checks driven by the inventory.
- [x] 3.2 Support first-version probe types for TCP connect, HTTP/HTTPS endpoint status, DNS query, and read-only API health endpoints where practical.
- [x] 3.3 Report per-service health results as passed, failed, unreachable, or skipped.
- [x] 3.4 Ensure online checks do not deploy, restart, upgrade, restore, reconfigure, or delete any foundation service or infrastructure state.
- [x] 3.5 Document that foundation health checks require live internal network context and are separate from offline validation.

## 4. Command Surface and Documentation

- [x] 4.1 Add Make targets for foundation inventory generation, offline checking, and explicit online health checking.
- [x] 4.2 Include foundation offline checks in the appropriate offline validation path without requiring internal infrastructure access or runtime secrets.
- [x] 4.3 Update documentation to link the generated foundation recovery reference and explain the offline vs online command boundary.
- [x] 4.4 Keep implementation documentation clear that this change does not deploy K3s, mutate foundation services, or automate service lifecycle operations.

## 5. Tests and Validation

- [x] 5.1 Add unit tests for valid foundation inventory parsing and rendering.
- [x] 5.2 Add negative tests for duplicate names, unresolved dependencies, missing required metadata, duplicate restore order, inconsistent storage-network facts, and secret-like values.
- [x] 5.3 Add tests proving generated Markdown escapes table-sensitive content and remains non-sensitive.
- [x] 5.4 Add tests for health-check result classification using fake/local probe implementations without requiring internal infrastructure.
- [x] 5.5 Run `uv run openspec validate add-foundation-recovery-checks`.
- [x] 5.6 Run the repository offline validation target.
- [x] 5.7 Confirm the diff does not change K3s manifests, OPNsense/TrueNAS/DNS/Harbor/Auth/sing-box runtime state, PVE/OpenTofu resources, switch automation behavior, or live infrastructure behavior.

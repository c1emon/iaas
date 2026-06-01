## Context

The repository already manages selected OPNsense resources through Ansible using local execution, environment-provided API credentials, and the `oxlorg.opnsense` collection. Existing write automation is conservative: firewall aliases are sourced from a hand-written vars file, applied additively, and reloaded only after successful changes. OPNsense exports are treated as observations, not as direct apply input.

OPNsense Virtual IPs are currently outside the managed scope, but IP Alias VIPs fit the existing model better than DNAT, firewall rules, or interface/VLAN configuration. The `oxlorg.opnsense.interface_vip` module provides a stable, idempotent interface for VIPs and supports IP Alias mode directly.

## Goals / Non-Goals

**Goals:**

- Add a narrow Ansible workflow for OPNsense IP Alias VIP management.
- Use `opnsense_vips` as the hand-written desired-state variable.
- Force all managed VIPs to `mode: ipalias` at the playbook/module boundary.
- Support explicit `state: present` and `state: absent` for entries declared in `opnsense_vips`.
- Preserve unmanaged VIPs by avoiding purge or authoritative reconciliation.
- Reuse existing OPNsense credential preflight, module defaults, snapshot guidance, and validation patterns.
- Document the safety boundary and operator commands.

**Non-Goals:**

- Managing CARP, Proxy ARP, or Other VIP modes.
- Managing DNAT, NAT, firewall rules, interface assignments, VLANs, WAN/PPPoE, or management access rules.
- Auto-generating desired VIP state from export artifacts.
- Purging VIPs absent from `opnsense_vips`.
- Introducing a new Ansible collection or custom module.

## Decisions

### Use `opnsense_vips` as the desired-state variable

The variable will be named `opnsense_vips` rather than a narrower name such as `opnsense_ip_alias_vips`. This keeps the public configuration simple while the workflow itself enforces the narrower v1 boundary of IP Alias only.

Alternative considered: `opnsense_ip_alias_vips`. This would encode the scope in the variable name, but the chosen name is shorter and leaves room for future evolution if a later change intentionally expands the capability.

### Keep desired state hand-written

VIP desired state will live in a repository vars file under `ansible/vars/opnsense/`, parallel to alias desired state. Exported or observed live configuration may inform migration, but it will not be read directly by the apply workflow.

Alternative considered: generate `vips.yml` from an export. This was rejected because generated live-state artifacts may include unmanaged or sensitive network topology and should not become authoritative without review.

### Force IP Alias mode in the workflow

The playbook will call `oxlorg.opnsense.interface_vip` with `mode: ipalias` for every declared entry. The desired-state schema will not require operators to set `mode` for v1.

Alternative considered: allow `mode` in each entry and assert it equals `ipalias`. This is more explicit but invites accidental expansion into CARP or Proxy ARP semantics. Forcing the module argument keeps the boundary clear.

### Use explicit absent, not purge

The workflow will support `state: absent` only for VIPs explicitly listed in `opnsense_vips`. It will not delete or modify VIPs that are missing from the vars file.

Alternative considered: add a purge mode for unmanaged VIPs. This was rejected for v1 because VIPs may be manually owned, CARP-related, or service-critical.

### Batch reload after changes

Individual VIP module calls should avoid immediate reload where practical, register their results, and reload the `interface_vip` target once if any declared VIP changed.

Alternative considered: rely on the module default reload behavior. A single explicit reload is easier to reason about and aligns with the existing alias workflow.

## Risks / Trade-offs

- **VIPs are interface-adjacent and can affect reachability** → Keep the scope to IP Alias only, require reviewed YAML, and document snapshot-before-write guidance.
- **Manual and Ansible ownership may overlap** → Manage only declared VIPs and document that unmanaged VIPs are preserved.
- **Accidental CARP or Proxy ARP management** → Do not expose mode selection in v1 and force `mode: ipalias` in the workflow.
- **Deleting the wrong VIP via `state: absent` could disrupt services** → Require explicit address/interface/description in desired state and avoid purge semantics.
- **Reload target semantics may differ from aliases** → Use the collection-supported `interface_vip` reload target and validate with syntax/lint checks before apply.

## Migration Plan

1. Operators review existing OPNsense VIPs manually or through read-only tooling.
2. Operators add only selected IP Alias VIPs to `ansible/vars/opnsense/vips.yml` using `opnsense_vips`.
3. Operators run the existing OPNsense snapshot workflow before the first write.
4. Operators validate the VIP playbook and vars with the documented syntax and lint commands.
5. Operators run the VIP management playbook to create, update, or explicitly remove declared IP Alias VIPs.

Rollback is manual and explicit: restore from an OPNsense snapshot/savepoint or declare the affected VIP with the desired previous values or `state: absent`, then re-run the workflow.

## Open Questions

- Should a later change extend the read-only export workflow to include VIP observations for migration review?
- Should future CARP support be a separate capability with HA-specific requirements and secret handling?

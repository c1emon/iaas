## Context

The repository now has uv-managed Ansible tooling, `oxlorg.opnsense`, a 1Password-backed `.env.opnsense.tpl`, and two working OPNsense bootstrap playbooks: a read-only alias smoke test and a configuration snapshot playbook. Manual exploration confirmed that the API can read firewall aliases, Unbound host overrides, Unbound forwarding entries, DHCPv4 leases, DHCPv6 leases, and DHCPv6 prefix leases.

The live firewall currently uses ISC DHCP for IPv4 and DHCPv6 behavior, with no ISC static mappings, DHCP ranges following a `.100` to `.220` convention, and active IPv6 IA_NA plus IA_PD leases. Kea is disabled and empty. Because DHCP and prefix delegation affect client connectivity, they should be recorded as facts only during this change.

## Goals / Non-Goals

**Goals:**

- Provide a repeatable, read-only export path for selected OPNsense configuration and facts.
- Export first-stage declarative-management candidates: firewall aliases, Unbound host overrides, and Unbound forwarding entries.
- Export DHCP lease and prefix facts for review without treating them as desired state.
- Keep raw export output local and ignored by default.
- Make the workflow safe to run before any future OPNsense management change.

**Non-Goals:**

- Do not modify OPNsense configuration.
- Do not create apply/reconcile playbooks for aliases, Unbound, DHCP, firewall rules, NAT, interfaces, or services.
- Do not migrate ISC DHCP to Kea or Dnsmasq.
- Do not manage DHCPv4 ranges, DHCPv6, router advertisements, or prefix delegation.
- Do not commit raw exports that contain hostnames, MAC addresses, lease data, or topology details.

## Decisions

### Use Ansible as the export entry point

Use a dedicated playbook, likely `ansible/playbooks/opnsense-export.yml`, rather than ad-hoc shell commands.

Rationale: it reuses the existing inventory, 1Password env injection, uv runtime, and `oxlorg.opnsense` module defaults. It also makes the export command repeatable for local use and future runner use.

Alternative considered: standalone Python script calling the OPNsense API. This would offer more control over JSON shaping but duplicates authentication, inventory, and collection behavior already provided by Ansible.

### Separate raw exports from curated desired-state variables

Raw API output should be written under an ignored local export directory, for example `exports/opnsense/`. Curated variables for later management should be a separate, explicit step and not produced as committed desired state by default.

Rationale: raw exports can contain sensitive operational facts, including MAC addresses, hostnames, lease state, IPv6 prefixes, and live topology. They also include runtime fields that are not suitable module input, such as UUIDs, counters, timestamps, selected-value maps, and lease timers.

Alternative considered: commit generated YAML variables immediately. This is risky because it could accidentally commit sensitive or noisy runtime data and imply ownership before review.

### Treat DHCP as observed facts only

The export may include DHCPv4 leases, DHCPv6 leases, and DHCPv6 prefix leases, but should label them as facts rather than managed configuration.

Rationale: DHCP currently has no static mappings and includes IPv6 prefix delegation behavior. That makes DHCP migration or management a separate design problem. The first-stage management candidates remain aliases and Unbound configuration.

Alternative considered: export DHCP into desired-state scopes. This would be premature without modeling IPv6 PD, RA behavior, and ISC/Dnsmasq/Kea backend choice.

### Prefer explicit target list

The export should use a small explicit list of known-good API targets instead of trying to discover or dump all OPNsense configuration.

Initial targets:

- `alias`
- `unbound_host`
- `unbound_forward`
- `dhcpv4/leases/search_lease` via raw API
- `dhcpv6/leases/search_lease` via raw API
- `dhcpv6/leases/search_prefix` via raw API

Rationale: broad exports increase permission scope and risk leaking unrelated configuration. Explicit targets match the current first-stage management scope.

## Risks / Trade-offs

- Raw exports may contain sensitive topology or client data → keep `exports/` ignored by default and document review requirements before promoting any data.
- API permissions may differ by OPNsense version or user privilege → fail clearly per target and allow partial exports to guide least-privilege permission updates.
- API output is not directly reusable as module input → defer cleaning into curated variables until after review.
- DHCP facts may be mistaken for desired state → separate output naming and documentation should mark DHCP as observed-only.
- Runner execution may later need 1Password Service Account integration → keep local `op run` workflow now and avoid runner-specific assumptions in this change.

## Migration Plan

1. Add ignore rules for local export artifacts.
2. Add a read-only export playbook that writes selected outputs locally.
3. Add documentation describing how to run the export and how to interpret output categories.
4. Validate playbook syntax and linting locally.
5. Run the export manually and review output outside Git.

Rollback is simple: remove the playbook, docs, and ignore rules. Since the change is read-only, there is no OPNsense state to roll back.

## Open Questions

- Should curated desired-state variables for aliases and Unbound be generated by a helper script in a later change, or written manually after reviewing raw exports?
- Should raw exports be JSON, YAML, or both?
- Should the export playbook continue on individual target failures to support least-privilege iteration, or fail fast to surface permission gaps?

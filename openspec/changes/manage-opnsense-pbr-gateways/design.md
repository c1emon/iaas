## Context

The repository already uses a conservative Ansible pattern for OPNsense automation: local execution, environment-provided API credentials, hand-written desired-state files, shared credential preflight, and additive writes only for explicitly declared resources. Firewall aliases and IP Alias VIPs are managed this way; firewall rules, NAT, routes, interfaces, VLANs, and default routing remain outside the managed boundary.

The proxy gateway design in `/Users/clemon/Workplace/sing-gateway/docs/opnsense-proxy-gateway.md` uses OPNsense as the owner of per-subnet Proxy Gateway VIPs and routes selected FakeIP TCP/UDP traffic to a Linux `sing-box` proxy gateway through policy-based routing. That PBR rule needs an OPNsense gateway object such as `GW_PROXY`, where the gateway IP is the proxy gateway's real DMZ/service-network address. This change only introduces management of that gateway object; PBR firewall rules and DNAT remain separate future capabilities.

## Goals / Non-Goals

**Goals:**

- Add a narrow Ansible workflow for OPNsense gateway objects intended for PBR next-hop use.
- Use `opnsense_gateways` as the hand-written desired-state variable.
- Use the official `oxlorg.opnsense.gateway` module rather than raw API calls.
- Support explicit `state: present` and `state: absent` for entries declared in `opnsense_gateways`.
- Preserve unmanaged gateways by avoiding purge or authoritative reconciliation.
- Require declared PBR gateways to set `default_gw: false` so this workflow does not claim default-route ownership.
- Reuse existing OPNsense credential preflight, module defaults, snapshot guidance, and validation patterns.
- Document that gateway `interface` values are OPNsense interface identifiers / network port values, not UI display names.

**Non-Goals:**

- Managing firewall PBR rules, including FakeIP rule order or gateway references in rules.
- Managing DNAT / port-forward, outbound NAT, or firewall filter rules.
- Managing default WAN gateways, default route selection, static routes, or gateway groups.
- Managing interfaces, VLANs, CARP, Proxy ARP, or other VIP modes.
- Auto-generating desired gateway state from export artifacts.
- Purging gateways absent from `opnsense_gateways`.
- Implementing automatic fail-open or fail-closed automation beyond the declared gateway object's monitor fields.
- Introducing a new Ansible collection or custom module.

## Decisions

### Use `opnsense_gateways` as hand-written desired state

Gateway desired state will live in `ansible/vars/opnsense/gateways.yml`, parallel to `aliases.yml` and `vips.yml`. The workflow will not read generated exports as apply input.

Alternative considered: embedding gateway declarations in a future PBR rules file. This was rejected because gateway objects are reusable dependencies and should be reviewed/applied before firewall rules reference them.

### Scope the capability to PBR gateway objects

The change name and documentation will frame this as PBR gateway management rather than full gateway/routing management. This keeps the v1 boundary aligned with the FakeIP PBR architecture: create `GW_PROXY`-style objects that later rules can select as next-hop gateways.

Alternative considered: a broad gateway management workflow that includes WAN/default gateways and gateway groups. This was rejected because default routing and gateway groups can disrupt internet access and need separate safety requirements.

### Require `default_gw: false`

Each declared gateway must include `default_gw`, and the playbook will assert that all declared entries set it to `false`. This makes the no-default-route boundary explicit in reviewed YAML.

Alternative considered: forcing `default_gw: false` in the module call and omitting it from desired state. This is safer at runtime but less visible during review. Requiring the field and asserting false makes the constraint auditable.

### Keep interface values as OPNsense identifiers

The `interface` field will use the value accepted by the official `oxlorg.opnsense.gateway` module and OPNsense API, such as `lan`, `wan`, `opt1`, or `opt2`. The workflow will not resolve UI display names such as `LAN_A` or `DMZ`.

Alternative considered: local interface display-name mapping. This was rejected for v1 to avoid an unverified name-resolution layer and to match the existing VIP workflow boundary.

### Batch reload after changes

Individual gateway module calls should pass `reload: false`, register their results, and reload the `gateway` target once if any declared gateway changed.

Alternative considered: relying on the module default reload behavior. A single explicit reload is easier to reason about and aligns with the existing alias and VIP workflows.

### Preserve monitor fields without deciding failover strategy

The desired-state schema will include monitor-related fields supported by `oxlorg.opnsense.gateway`, but this workflow will not promise automatic fail-open behavior. Operators can choose values such as `monitor_disable: true` for a fail-closed-like blackhole behavior if the proxy is unavailable, or later introduce a separate failover capability.

Alternative considered: designing gateway monitoring and PBR rule disablement together. This was rejected because it crosses into firewall rule automation and operational policy.

## Risks / Trade-offs

- **Wrong gateway interface or IP can blackhole PBR traffic** → Require reviewed YAML, interface identifier documentation, and snapshot-before-write guidance.
- **Accidental default route ownership could disrupt internet access** → Require and assert `default_gw: false` for every declared gateway.
- **Manual and Ansible ownership may overlap** → Manage only declared gateways and document that unmanaged gateways are preserved.
- **Gateway monitor behavior affects fail-open/fail-closed semantics** → Expose monitor fields but keep failover automation out of scope.
- **Deleting a referenced gateway via `state: absent` can break PBR rules** → Require explicit declaration and avoid purge semantics; operators must remove or update dependent rules separately.

## Migration Plan

1. Operators identify the proxy gateway's real OPNsense-reachable address, such as `10.255.255.10`, and the OPNsense interface identifier for that network.
2. Operators add selected PBR gateway objects to `ansible/vars/opnsense/gateways.yml` using `opnsense_gateways`.
3. Operators run the existing OPNsense snapshot workflow before the first write.
4. Operators validate the gateway playbook and vars with the documented syntax and lint commands.
5. Operators run the gateway management playbook to create, update, or explicitly remove declared PBR gateway objects.

Rollback is manual and explicit: restore from an OPNsense snapshot/savepoint or declare the affected gateway with the desired previous values or `state: absent`, then re-run the workflow. Firewall rules that reference a removed gateway must be handled separately.

## Open Questions

- Should a later PBR firewall rule capability assert that referenced gateways already exist in `opnsense_gateways` or live OPNsense state?
- Should future fail-open support be modeled through gateway groups, rule toggling, or an external health-check automation workflow?
- Should read-only export later include gateway observations for migration review without becoming apply input?

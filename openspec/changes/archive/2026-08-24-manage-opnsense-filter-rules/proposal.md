## Why

OPNsense 26.1 promotes API-backed firewall filter rules into the new rules UI, making it possible to manage selected pass/block/reject rules from reviewed Ansible desired state. The current repository manages related OPNsense dependencies such as aliases, VIPs, and PBR gateways, but filter rule ordering and gateway references still rely on manual configuration that can drift.

## What Changes

- Add a conservative Ansible workflow for managing explicitly declared OPNsense new firewall filter rules.
- Introduce `opnsense_filter_rules` as a hand-written desired-state variable under `ansible/vars/opnsense/`.
- Use `oxlorg.opnsense.rule_multi` against OPNsense new filter rules / Rules `[new]` / `/api/firewall/filter/*`.
- Use `description` as the immutable rule identity with strict format `iaas:opnsense:filter:<scope>:<slug>` and `match_fields: ['description']`.
- Validate that managed rule descriptions are present, globally unique, and match the required identity format before any write.
- Require declared rules to include explicit `state`, `enabled`, `sequence`, interface, action, protocol, source, and destination fields.
- Support ordered rules through `sequence`, while ensuring `sequence` is not part of the matching identity.
- Preserve unmanaged OPNsense filter rules by avoiding purge or reconciliation of entries absent from `opnsense_filter_rules`.
- Document that legacy rules, outbound NAT, DNAT/port-forward, gateway creation, interfaces, VLANs, static routes, and gateway groups remain out of scope.

## Capabilities

### New Capabilities
- `opnsense-filter-rule-management`: Defines safe, additive management of OPNsense new firewall filter rules from hand-written Ansible desired state with strict description-based identities and sequence-based ordering.

### Modified Capabilities
- None.

## Impact

- Adds an Ansible desired-state file under `ansible/vars/opnsense/` for managed filter rule declarations.
- Adds an OPNsense filter rule management playbook under `ansible/playbooks/opnsense/`.
- Updates OPNsense management documentation and playbook README guidance.
- Uses the existing `oxlorg.opnsense` collection and environment-provided OPNsense API credentials.
- Introduces write operations against OPNsense API-backed firewall filter rules, scoped to explicitly declared managed rules only.

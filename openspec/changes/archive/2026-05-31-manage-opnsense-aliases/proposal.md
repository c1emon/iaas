## Why

OPNsense firewall aliases are already exported as first-stage declarative-management candidates, but the repository does not yet provide a safe way to apply desired alias definitions back to OPNsense. A small additive alias workflow lets operators manage known aliases from reviewed YAML without taking ownership of all existing firewall aliases.

## What Changes

- Add an Ansible workflow for creating or updating OPNsense firewall aliases from a hand-written YAML source file.
- Use environment-provided OPNsense API credentials and existing inventory/group variable conventions.
- Apply alias changes additively: aliases listed in the YAML source are created or updated, while aliases not listed are left untouched.
- Reload the OPNsense alias target after successful changes so updates become active.
- Document usage, supported scope, validation commands, and safety boundaries.
- Do not add purge/delete behavior for aliases outside the desired YAML list.
- Do not manage firewall rules, NAT, interfaces, or other OPNsense configuration in this change.

## Capabilities

### New Capabilities
- `opnsense-alias-management`: Additive management of OPNsense firewall aliases from a hand-written YAML desired-state file.

### Modified Capabilities
- `opnsense-config-export`: Document the relationship between exported firewall aliases and the new hand-written alias management source, without changing export behavior.

## Impact

- Affected areas: `ansible/playbooks/opnsense/`, Ansible variable files, OPNsense playbook documentation, and OpenSpec documentation for OPNsense workflows.
- External systems: OPNsense firewall API, via the existing `oxlorg.opnsense` Ansible collection.
- Dependencies: no new dependency is expected beyond the existing uv-managed Ansible/OPNsense toolchain.
- Safety: the workflow must not store API credentials in repository files and must not delete or purge aliases that are absent from the hand-written YAML source.

## Why

OPNsense Virtual IPs are a natural next step for conservative network automation because IP Alias VIPs are stable, declarative objects that can be managed by `oxlorg.opnsense.interface_vip` without touching firewall rules, NAT, interfaces, or VLANs. Managing reviewed IP Alias VIPs from source-controlled desired state reduces manual drift while preserving the current safety boundary around public ingress and lower-level interface configuration.

## What Changes

- Add a new Ansible workflow for managing OPNsense IP Alias VIPs from a hand-written desired-state YAML file.
- Introduce `opnsense_vips` as the desired-state variable for VIP entries.
- Use `oxlorg.opnsense.interface_vip` with IP Alias mode only.
- Support explicit `state: present` and `state: absent` for declared VIPs.
- Preserve unmanaged OPNsense VIPs by avoiding purge or reconciliation of entries absent from `opnsense_vips`.
- Document the VIP management workflow, safety boundary, validation commands, and unsupported VIP modes.
- Keep CARP, Proxy ARP, Other VIP modes, DNAT, NAT, firewall rules, interfaces, and VLANs out of scope.

## Capabilities

### New Capabilities
- `opnsense-vip-management`: Defines safe, additive management of OPNsense IP Alias Virtual IPs from hand-written Ansible desired state.

### Modified Capabilities
- None.

## Impact

- Adds an Ansible desired-state file under `ansible/vars/opnsense/` for VIP declarations.
- Adds an OPNsense VIP management playbook under `ansible/playbooks/opnsense/`.
- Updates OPNsense management documentation and playbook README guidance.
- Uses the existing `oxlorg.opnsense` collection and environment-provided OPNsense API credentials.
- Introduces write operations against OPNsense VIP settings, scoped to explicitly declared IP Alias VIPs only.

## Why

FakeIP PBR needs a stable OPNsense gateway object, such as `GW_PROXY`, so firewall rules can route selected TCP/UDP traffic to the proxy gateway while preserving the original destination address. Managing that gateway from reviewed desired state reduces manual drift without expanding automation into firewall rules, NAT, routes, or interface ownership.

## What Changes

- Add a conservative Ansible workflow for managing explicitly declared OPNsense gateway objects intended for policy-based routing.
- Introduce `opnsense_gateways` as a hand-written desired-state variable under `ansible/vars/opnsense/`.
- Use the official `oxlorg.opnsense.gateway` module, not raw API calls.
- Support explicit `state: present` and `state: absent` for declared gateways.
- Preserve unmanaged OPNsense gateways by avoiding purge or reconciliation of entries absent from `opnsense_gateways`.
- Require PBR gateway entries to avoid default-route ownership by declaring `default_gw: false`.
- Document that firewall rules, DNAT, outbound NAT, static routes, gateway groups, interfaces, VLANs, and automatic fail-open behavior remain out of scope.

## Capabilities

### New Capabilities
- `opnsense-pbr-gateway-management`: Defines safe, additive management of OPNsense gateway objects used as PBR next-hops from hand-written Ansible desired state.

### Modified Capabilities
- None.

## Impact

- Adds an Ansible desired-state file under `ansible/vars/opnsense/` for PBR gateway declarations.
- Adds an OPNsense gateway management playbook under `ansible/playbooks/opnsense/`.
- Updates OPNsense management documentation and playbook README guidance.
- Uses the existing `oxlorg.opnsense` collection and environment-provided OPNsense API credentials.
- Introduces write operations against OPNsense routing gateway settings, scoped to explicitly declared PBR gateway objects only.

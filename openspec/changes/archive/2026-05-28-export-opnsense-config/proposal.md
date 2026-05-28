## Why

OPNsense is already reachable through Ansible and 1Password-backed API credentials, but its existing configuration is still only observable through the live firewall. We need a safe first step that exports current low-risk configuration into reviewable artifacts before any attempt to manage or reconcile OPNsense declaratively.

## What Changes

- Add a read-only OPNsense export capability for selected configuration and operational facts.
- Export firewall aliases, Unbound host overrides, and Unbound forwarding entries as the first declarative-management candidates.
- Export DHCPv4 leases, DHCPv6 leases, and DHCPv6 prefix leases as facts only, not as managed configuration.
- Keep generated export files out of Git by default so live topology and client information can be reviewed before deciding what to commit.
- Document that ISC DHCP, DHCPv6, prefix delegation, interfaces, firewall rules, and NAT remain outside first-stage management.
- No live OPNsense configuration is changed by this proposal.

## Capabilities

### New Capabilities

- `opnsense-config-export`: Read-only export of selected OPNsense configuration and facts into local review artifacts.

### Modified Capabilities

- None.

## Impact

- Affects Ansible playbooks and documentation under `ansible/` and `docs/`.
- Uses the existing `oxlorg.opnsense` collection, uv-managed Ansible runtime, and 1Password environment injection.
- Produces local export artifacts that may contain network topology, hostnames, client lease data, MAC addresses, and IPv6 prefixes; these artifacts must be ignored unless explicitly sanitized and promoted.
- Does not change OPNsense, Terraform resources, runner configuration, or real infrastructure state.

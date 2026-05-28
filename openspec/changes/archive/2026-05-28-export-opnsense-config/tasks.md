## 1. Export Storage Safety

- [x] 1.1 Add Git ignore rules for local OPNsense export artifacts under an `exports/` path.
- [x] 1.2 Document that raw exports may contain topology, lease, hostname, MAC address, and IPv6 prefix data.

## 2. Read-only Export Workflow

- [x] 2.1 Add `ansible/playbooks/opnsense-export.yml` with environment credential assertions.
- [x] 2.2 Export firewall aliases using `oxlorg.opnsense.list` target `alias`.
- [x] 2.3 Export Unbound host overrides using `oxlorg.opnsense.list` target `unbound_host`.
- [x] 2.4 Export Unbound forwarding entries using `oxlorg.opnsense.list` target `unbound_forward`.
- [x] 2.5 Export DHCPv4 lease facts using the read-only raw API endpoint `dhcpv4/leases/search_lease`.
- [x] 2.6 Export DHCPv6 lease facts using the read-only raw API endpoint `dhcpv6/leases/search_lease`.
- [x] 2.7 Export DHCPv6 prefix lease facts using the read-only raw API endpoint `dhcpv6/leases/search_prefix`.
- [x] 2.8 Write export results into the ignored local export directory without marking DHCP facts as managed desired state.

## 3. Documentation

- [x] 3.1 Update OPNsense management documentation with the export command and expected output location.
- [x] 3.2 Document first-stage management candidates: aliases, Unbound host overrides, and Unbound forwarding.
- [x] 3.3 Document observed-only DHCP facts and explicitly exclude ISC DHCP, DHCPv6, prefix delegation, interfaces, firewall rules, and NAT from this change.

## 4. Validation

- [x] 4.1 Run `uv run yamllint .`.
- [x] 4.2 Run `uv run ansible-lint ansible/playbooks/opnsense-export.yml`.
- [x] 4.3 Run `cd ansible && uv run ansible-playbook --syntax-check playbooks/opnsense-export.yml`.
- [x] 4.4 Run the export manually with `op run --env-file .env.opnsense.tpl` and verify it completes without live OPNsense configuration changes.
- [x] 4.5 Verify generated export artifacts remain ignored by Git status.

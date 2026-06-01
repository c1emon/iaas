## 1. Desired State

- [x] 1.1 Create `ansible/vars/opnsense/vips.yml` with an `opnsense_vips` list and documented IP Alias examples.
- [x] 1.2 Ensure the sample VIP entries include `description`, `interface`, `address` with CIDR, `bind`, `expand`, and `state` fields.

## 2. VIP Management Playbook

- [x] 2.1 Create `ansible/playbooks/opnsense/manage-vips.yml` using the existing OPNsense module defaults and local connection pattern.
- [x] 2.2 Load `vars/opnsense/vips.yml` and reuse `tasks/api-credential-preflight.yml` before any write operation.
- [x] 2.3 Add assertions that `opnsense_vips` is defined as a sequence and that each VIP defines required IP Alias management fields.
- [x] 2.4 Apply declared VIPs with `oxlorg.opnsense.interface_vip`, forcing `mode: ipalias` and passing explicit `present` or `absent` state.
- [x] 2.5 Preserve unmanaged VIPs by avoiding purge, bulk reconciliation, or deletes for entries absent from `opnsense_vips`.
- [x] 2.6 Register VIP apply results and reload the `interface_vip` target once only when declared VIPs changed.

## 3. Documentation

- [x] 3.1 Update `ansible/playbooks/opnsense/README.md` with VIP workflow usage, input file, safety boundary, and validation commands.
- [x] 3.2 Update `docs/opnsense-management.md` to include IP Alias VIPs in the managed scope and clarify that CARP, Proxy ARP, DNAT, NAT, firewall rules, interfaces, and VLANs remain out of scope.
- [x] 3.3 Document that VIP desired state is hand-written and is not generated from export artifacts.

## 4. Validation

- [x] 4.1 Run `uv run ansible-playbook --syntax-check playbooks/opnsense/manage-vips.yml` from `ansible/`.
- [x] 4.2 Run `uv run yamllint vars/opnsense/vips.yml playbooks/opnsense/manage-vips.yml` from `ansible/`.
- [x] 4.3 Run `uv run ansible-lint playbooks/opnsense/manage-vips.yml` from `ansible/`.
- [x] 4.4 Run `openspec status --change manage-opnsense-ip-alias-vips` and confirm the change is apply-ready.

## 1. Desired State

- [x] 1.1 Create `ansible/vars/opnsense/gateways.yml` with an `opnsense_gateways` list and documented PBR gateway examples.
- [x] 1.2 Ensure the sample gateway entries include `name`, `interface`, `ip_protocol`, `gateway`, `default_gw`, `far_gw`, monitor fields, `priority`, `weight`, `description`, and `state` fields.
- [x] 1.3 Document that `interface` uses OPNsense interface identifiers / network port values such as `lan`, `wan`, or `opt1`, not UI display names.

## 2. Gateway Management Playbook

- [x] 2.1 Create `ansible/playbooks/opnsense/manage-gateways.yml` using the existing OPNsense module defaults and local connection pattern.
- [x] 2.2 Load `vars/opnsense/gateways.yml` and reuse `tasks/api-credential-preflight.yml` before any write operation.
- [x] 2.3 Add assertions that `opnsense_gateways` is defined as a sequence and that each gateway defines required PBR gateway management fields.
- [x] 2.4 Add assertions that each gateway has `state` set to `present` or `absent` and `default_gw` set to `false`.
- [x] 2.5 Apply declared gateways with `oxlorg.opnsense.gateway`, passing explicit `present` or `absent` state and using `reload: false` per gateway.
- [x] 2.6 Preserve unmanaged gateways by avoiding purge, bulk reconciliation, or deletes for entries absent from `opnsense_gateways`.
- [x] 2.7 Register gateway apply results and reload the `gateway` target once only when declared gateways changed.

## 3. Documentation

- [x] 3.1 Update `ansible/playbooks/opnsense/README.md` with gateway workflow usage, input file, safety boundary, and validation commands.
- [x] 3.2 Update `docs/opnsense-management.md` to include PBR gateway objects in the managed scope and clarify that firewall rules, DNAT, NAT, static routes, gateway groups, interfaces, and VLANs remain out of scope.
- [x] 3.3 Document the FakeIP PBR relationship: aliases and VIPs are prerequisites, gateways provide the `GW_PROXY` next-hop, and PBR firewall rules remain a separate future capability.
- [x] 3.4 Document that gateway desired state is hand-written and is not generated from export artifacts.

## 4. Validation

- [x] 4.1 Run `uv run ansible-playbook --syntax-check playbooks/opnsense/manage-gateways.yml` from `ansible/`.
- [x] 4.2 Run `uv run yamllint vars/opnsense/gateways.yml playbooks/opnsense/manage-gateways.yml` from `ansible/`.
- [x] 4.3 Run `uv run ansible-lint playbooks/opnsense/manage-gateways.yml` from `ansible/`.
- [x] 4.4 Run `openspec status --change manage-opnsense-pbr-gateways` and confirm the change is apply-ready.

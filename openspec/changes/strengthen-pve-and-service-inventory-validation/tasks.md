## 1. PVE Inventory Validation Policy

- [ ] 1.1 Define VM name/hostname validation policy as a lower-case DNS-label-safe value compatible with current VM names.
- [ ] 1.2 Define Ansible inventory group validation policy as lower-case Ansible-safe group identifiers compatible with current groups.
- [ ] 1.3 Define PVE tag validation policy against the current PVE/OpenTofu provider-safe token set.
- [ ] 1.4 Define duplicate handling for VM string-list fields, rejecting duplicate `ansible_groups` and `tags` with field-context validation errors.

## 2. PVE Inventory Validation Behavior

- [ ] 2.1 Reject invalid VM names before generation, including empty, uppercase, whitespace, underscore, dot, leading/trailing hyphen, and overlong hostname labels.
- [ ] 2.2 Reject invalid Ansible group values, including empty strings, non-strings, whitespace, hyphenated names, and duplicate groups within one VM.
- [ ] 2.3 Reject invalid PVE tag values, including empty strings, non-strings, whitespace, commas/delimiters, and duplicate tags within one VM.
- [ ] 2.4 Strengthen `static_ip` validation so malformed CIDR, wrong prefix, outside-network, duplicate, network-address, and broadcast-address values fail with VM/field context.
- [ ] 2.5 Preserve normalized model keys and generated OpenTofu, Ansible, PVE VM docs, and template env output shape for unchanged valid inventory.

## 3. Services Markdown Rendering

- [ ] 3.1 Add a Markdown table-cell escaping helper local to service rendering or an appropriate primitive helper if one already exists.
- [ ] 3.2 Escape service endpoint row cells, including service name, owner VM, endpoint label, FQDN, protocol, exposure, auth, and review hints.
- [ ] 3.3 Escape warning row cells, including service, endpoint, code, and message.
- [ ] 3.4 Preserve existing `-` placeholders for omitted optional display values.

## 4. Tests and Validation

- [ ] 4.1 Add negative tests for invalid VM name/hostname values.
- [ ] 4.2 Add negative tests for invalid and duplicate Ansible group values.
- [ ] 4.3 Add negative tests for invalid and duplicate PVE tag values.
- [ ] 4.4 Add negative tests for static IP prefix mismatch, network/broadcast address, outside-network address, duplicate address, and malformed CIDR context.
- [ ] 4.5 Add service renderer tests proving `|`, newline, and carriage-return characters do not break Markdown table structure.
- [ ] 4.6 Confirm current `inventory/vms.yml` and `inventory/services.yml` remain valid.
- [ ] 4.7 Run the focused Python test subsets for PVE inventory and services inventory.
- [ ] 4.8 Run `make check`.
- [ ] 4.9 Run `openspec validate strengthen-pve-and-service-inventory-validation`.

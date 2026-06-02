## 1. Desired State Input

- [x] 1.1 Update `ansible/vars/opnsense/filter-rules.yml` examples to document that `source_port` and `destination_port` accept strings or lists.
- [x] 1.2 Add an example list containing a quoted numeric port, a range, and a port alias.
- [x] 1.3 Preserve omitted port fields as unrestricted ports in migrated rules.

## 2. Playbook Normalization

- [x] 2.1 Update `ansible/playbooks/opnsense/manage-filter-rules.yml` derived apply-list generation to normalize list-valued `source_port` to comma-separated strings.
- [x] 2.2 Update derived apply-list generation to normalize list-valued `destination_port` to comma-separated strings.
- [x] 2.3 Preserve existing omitted-port empty-string defaults.
- [x] 2.4 Preserve existing string-valued port behavior.
- [x] 2.5 Preserve existing identity generation, network-list normalization, invert defaults, uniqueness validation, reload-on-change, and unmanaged-rule behavior.

## 3. Documentation

- [x] 3.1 Update `ansible/playbooks/opnsense/README.md` to describe port fields accepting strings or lists.
- [x] 3.2 Update `docs/opnsense-management.md` to mention list input for source/destination ports.
- [x] 3.3 Document that omitted port fields still mean unrestricted ports.

## 4. Validation

- [x] 4.1 Run `uv run ansible-playbook --syntax-check playbooks/opnsense/manage-filter-rules.yml` from `ansible/`.
- [x] 4.2 Run `uv run yamllint vars/opnsense/filter-rules.yml playbooks/opnsense/manage-filter-rules.yml` from `ansible/`.
- [x] 4.3 Run `uv run ansible-lint playbooks/opnsense/manage-filter-rules.yml` from `ansible/`.
- [x] 4.4 Run `openspec status --change support-opnsense-filter-rule-port-arrays` and confirm the change is apply-ready.

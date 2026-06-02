## 1. Desired State Input

- [x] 1.1 Update `ansible/vars/opnsense/filter-rules.yml` examples to omit empty `source_port` and `destination_port` fields.
- [x] 1.2 Remove empty port fields from migrated filter rule entries.
- [x] 1.3 Keep explicit destination ports, port aliases, and port ranges where present.

## 2. Playbook Defaults

- [x] 2.1 Remove `source_port` and `destination_port` from `opnsense_filter_rule_required_fields`.
- [x] 2.2 Default omitted `source_port` to `""` in generated module input.
- [x] 2.3 Default omitted `destination_port` to `""` in generated module input.
- [x] 2.4 Preserve explicit port values when provided.
- [x] 2.5 Preserve existing identity generation, network-list normalization, invert defaults, uniqueness validation, reload-on-change, and unmanaged-rule behavior.

## 3. Documentation

- [x] 3.1 Update `ansible/playbooks/opnsense/README.md` to document optional port fields and default any-port behavior.
- [x] 3.2 Update `docs/opnsense-management.md` to mention that omitted port fields default to unrestricted ports.

## 4. Validation

- [x] 4.1 Run `uv run ansible-playbook --syntax-check playbooks/opnsense/manage-filter-rules.yml` from `ansible/`.
- [x] 4.2 Run `uv run yamllint vars/opnsense/filter-rules.yml playbooks/opnsense/manage-filter-rules.yml` from `ansible/`.
- [x] 4.3 Run `uv run ansible-lint playbooks/opnsense/manage-filter-rules.yml` from `ansible/`.
- [x] 4.4 Run `openspec status --change make-opnsense-filter-rule-ports-optional` and confirm the change is apply-ready.

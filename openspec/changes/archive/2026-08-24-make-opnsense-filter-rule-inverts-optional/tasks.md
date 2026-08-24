## 1. Desired State Input

- [x] 1.1 Update `ansible/vars/opnsense/filter-rules.yml` examples to omit `source_invert: false` and `destination_invert: false`.
- [x] 1.2 Remove false invert fields from migrated filter rule entries.
- [x] 1.3 Document that explicit `true` remains supported for inverted source or destination matching.

## 2. Playbook Defaults

- [x] 2.1 Remove `source_invert` and `destination_invert` from `opnsense_filter_rule_required_fields`.
- [x] 2.2 Default omitted `source_invert` to `false` in generated module input.
- [x] 2.3 Default omitted `destination_invert` to `false` in generated module input.
- [x] 2.4 Preserve explicit `true` or `false` invert values when provided.
- [x] 2.5 Preserve existing identity generation, network-list normalization, uniqueness validation, reload-on-change, and unmanaged-rule behavior.

## 3. Documentation

- [x] 3.1 Update `ansible/playbooks/opnsense/README.md` to document optional invert fields and default `false`.
- [x] 3.2 Update `docs/opnsense-management.md` to mention that invert fields may be omitted unless true is needed.

## 4. Validation

- [x] 4.1 Run `uv run ansible-playbook --syntax-check playbooks/opnsense/manage-filter-rules.yml` from `ansible/`.
- [x] 4.2 Run `uv run yamllint vars/opnsense/filter-rules.yml playbooks/opnsense/manage-filter-rules.yml` from `ansible/`.
- [x] 4.3 Run `uv run ansible-lint playbooks/opnsense/manage-filter-rules.yml` from `ansible/`.
- [x] 4.4 Run `openspec status --change make-opnsense-filter-rule-inverts-optional` and confirm the change is apply-ready.

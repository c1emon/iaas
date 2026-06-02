## 1. Desired State Input

- [x] 1.1 Update `ansible/vars/opnsense/filter-rules.yml` examples to document that `source_net` and `destination_net` accept strings or lists.
- [x] 1.2 Convert migrated rules with comma-separated `destination_net` values into YAML lists.
- [x] 1.3 Keep port fields as strings in examples and migrated rules.

## 2. Playbook Normalization

- [x] 2.1 Update `ansible/playbooks/opnsense/manage-filter-rules.yml` derived apply-list generation to normalize list-valued `source_net` to comma-separated strings.
- [x] 2.2 Update derived apply-list generation to normalize list-valued `destination_net` to comma-separated strings.
- [x] 2.3 Preserve existing string-valued `source_net` and `destination_net` behavior.
- [x] 2.4 Preserve existing identity generation, uniqueness validation, reload-on-change, and unmanaged-rule preservation behavior.

## 3. Documentation

- [x] 3.1 Update `ansible/playbooks/opnsense/README.md` to describe network fields accepting strings or lists.
- [x] 3.2 Update `docs/opnsense-management.md` to mention list input for source/destination networks.
- [x] 3.3 Document that port fields remain strings in this workflow.

## 4. Validation

- [x] 4.1 Run `uv run ansible-playbook --syntax-check playbooks/opnsense/manage-filter-rules.yml` from `ansible/`.
- [x] 4.2 Run `uv run yamllint vars/opnsense/filter-rules.yml playbooks/opnsense/manage-filter-rules.yml` from `ansible/`.
- [x] 4.3 Run `uv run ansible-lint playbooks/opnsense/manage-filter-rules.yml` from `ansible/`.
- [x] 4.4 Run `openspec status --change support-opnsense-filter-rule-net-arrays` and confirm the change is apply-ready.

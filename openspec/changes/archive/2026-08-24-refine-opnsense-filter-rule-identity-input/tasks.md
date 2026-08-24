## 1. Desired State Input

- [x] 1.1 Update `ansible/vars/opnsense/filter-rules.yml` examples to use `scope` and `slug` instead of full `description`.
- [x] 1.2 Document that `scope` and `slug` are immutable identity parts and generate the OPNsense `description`.
- [x] 1.3 Document that direct `description` input is rejected in `opnsense_filter_rules`.

## 2. Playbook Validation and Transformation

- [x] 2.1 Update `ansible/playbooks/opnsense/manage-filter-rules.yml` required fields by replacing `description` with `scope` and `slug`.
- [x] 2.2 Add assertions that each declared rule omits direct `description`.
- [x] 2.3 Add assertions that each `scope` and `slug` matches `^[a-z0-9][a-z0-9-]*$`.
- [x] 2.4 Build a derived module input list that removes `scope` and `slug` and adds generated `description` values.
- [x] 2.5 Validate generated descriptions are globally unique before any OPNsense API write.
- [x] 2.6 Apply declared rules with `oxlorg.opnsense.rule_multi` using the derived list, `match_fields: ['description']`, no purge controls, and `reload: false`.
- [x] 2.7 Preserve existing reload-on-change behavior and unmanaged-rule preservation behavior.

## 3. Documentation

- [x] 3.1 Update `ansible/playbooks/opnsense/README.md` to describe `scope`/`slug` input and generated descriptions.
- [x] 3.2 Update `docs/opnsense-management.md` to describe the shorter identity input model.
- [x] 3.3 Keep documentation clear that OPNsense still sees `description` as immutable identity with `match_fields: ['description']`.
- [x] 3.4 Keep UUID identity through `setRule/{uuid}` documented as out of scope.

## 4. Validation

- [x] 4.1 Run `uv run ansible-playbook --syntax-check playbooks/opnsense/manage-filter-rules.yml` from `ansible/`.
- [x] 4.2 Run `uv run yamllint vars/opnsense/filter-rules.yml playbooks/opnsense/manage-filter-rules.yml` from `ansible/`.
- [x] 4.3 Run `uv run ansible-lint playbooks/opnsense/manage-filter-rules.yml` from `ansible/`.
- [x] 4.4 Run `openspec status --change refine-opnsense-filter-rule-identity-input` and confirm the change is apply-ready.

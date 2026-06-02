## 1. Desired State

- [x] 1.1 Create `ansible/vars/opnsense/filter-rules.yml` with an `opnsense_filter_rules` list and documented examples for new OPNsense filter rules.
- [x] 1.2 Ensure example rules use strict immutable descriptions in `iaas:opnsense:filter:<scope>:<slug>` format.
- [x] 1.3 Include example sequence blocks and document that `sequence` controls order but is not rule identity.
- [x] 1.4 Document that the file is hand-written desired state and is not generated from `download_rules.csv` or `exports/opnsense/` artifacts.

## 2. Filter Rule Management Playbook

- [x] 2.1 Create `ansible/playbooks/opnsense/manage-filter-rules.yml` using the existing local OPNsense module defaults pattern.
- [x] 2.2 Load `vars/opnsense/filter-rules.yml` and reuse `tasks/api-credential-preflight.yml` before any write operation.
- [x] 2.3 Add assertions that `opnsense_filter_rules` is defined as a non-string sequence.
- [x] 2.4 Add assertions that each declared filter rule defines the required fields: `description`, `state`, `enabled`, `sequence`, `interface`, `direction`, `action`, `quick`, `ip_protocol`, `protocol`, `source_net`, `source_port`, `source_invert`, `destination_net`, `destination_port`, and `destination_invert`.
- [x] 2.5 Add assertions that each declared rule sets `state` to `present` or `absent`.
- [x] 2.6 Add assertions that every description matches `^iaas:opnsense:filter:[a-z0-9][a-z0-9-]*:[a-z0-9][a-z0-9-]*$`.
- [x] 2.7 Add assertions that declared descriptions are globally unique.
- [x] 2.8 Apply declared rules with `oxlorg.opnsense.rule_multi`, `match_fields: ['description']`, no purge controls, and `reload: false` during per-rule processing.
- [x] 2.9 Apply or reload the OPNsense filter target once only when declared filter rule changes occurred.
- [x] 2.10 Preserve unmanaged filter rules by avoiding purge, bulk reconciliation, or deletes for entries absent from `opnsense_filter_rules`.

## 3. Documentation

- [x] 3.1 Update `ansible/playbooks/opnsense/README.md` with filter rule workflow usage, input file, identity format, ordering guidance, and validation commands.
- [x] 3.2 Update `docs/opnsense-management.md` to include API-backed filter rules in the managed scope and clarify that legacy rules, NAT, DNAT, static routes, gateway groups, interfaces, and VLANs remain out of scope.
- [x] 3.3 Document that `description` is an immutable machine identity, not a human-readable sentence, while this workflow uses `match_fields: ['description']`.
- [x] 3.4 Document that future UUID identity through `setRule/{uuid}` is out of scope for this workflow.

## 4. Validation

- [x] 4.1 Run `uv run ansible-playbook --syntax-check playbooks/opnsense/manage-filter-rules.yml` from `ansible/`.
- [x] 4.2 Run `uv run yamllint vars/opnsense/filter-rules.yml playbooks/opnsense/manage-filter-rules.yml` from `ansible/`.
- [x] 4.3 Run `uv run ansible-lint playbooks/opnsense/manage-filter-rules.yml` from `ansible/`.
- [x] 4.4 Run `openspec status --change manage-opnsense-filter-rules` and confirm the change is apply-ready.

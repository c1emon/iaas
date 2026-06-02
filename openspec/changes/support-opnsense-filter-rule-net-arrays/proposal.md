## Why

Some OPNsense filter rule fields represent multiple networks as comma-separated strings, which is harder to review and edit safely in YAML. Supporting arrays for network fields makes desired state clearer while preserving the string format required by `oxlorg.opnsense.rule_multi`.

## What Changes

- Allow `source_net` and `destination_net` in `opnsense_filter_rules` to be either strings or YAML lists.
- Normalize list values into comma-separated strings before calling `oxlorg.opnsense.rule_multi`.
- Keep `source_port` and `destination_port` as strings for now to avoid ambiguity with port ranges.
- Update generated examples and current migrated filter rules to use arrays where multiple networks are listed.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `opnsense-filter-rule-management`: Support YAML list input for source and destination network fields while preserving module-compatible rule submission.

## Impact

- Updates `ansible/playbooks/opnsense/manage-filter-rules.yml` normalization logic.
- Updates `ansible/vars/opnsense/filter-rules.yml` examples and migrated rules.
- Updates OPNsense playbook documentation.

## Why

Some OPNsense filter rules may need to match multiple source or destination ports, aliases, or ranges. Supporting YAML arrays for port fields makes those cases easier to review while preserving the comma-separated string format expected by `oxlorg.opnsense.rule_multi`.

## What Changes

- Allow `source_port` and `destination_port` in `opnsense_filter_rules` to be either strings or YAML lists.
- Normalize list values into comma-separated strings before calling `oxlorg.opnsense.rule_multi`.
- Preserve omitted port fields as empty strings, meaning unrestricted ports.
- Update examples and documentation to show optional string-or-list port input.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `opnsense-filter-rule-management`: Support YAML list input for source and destination port fields while preserving optional any-port defaults and module-compatible rule submission.

## Impact

- Updates `ansible/playbooks/opnsense/manage-filter-rules.yml` normalization logic.
- Updates `ansible/vars/opnsense/filter-rules.yml` examples and comments.
- Updates OPNsense playbook documentation.

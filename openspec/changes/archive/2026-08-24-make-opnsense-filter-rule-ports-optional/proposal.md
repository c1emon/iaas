## Why

Most OPNsense filter rules do not restrict source ports, and many do not restrict destination ports. Requiring empty `source_port` and `destination_port` strings adds noise when the safe default is any port.

## What Changes

- Remove `source_port` and `destination_port` from required filter rule fields.
- Default omitted `source_port` and `destination_port` to empty strings in generated module input.
- Preserve explicit port numbers, ranges, and aliases when provided.
- Update examples, migrated rules, and documentation to omit empty port fields.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `opnsense-filter-rule-management`: Make source/destination port fields optional in desired state with default empty-string normalization before module submission.

## Impact

- Updates `ansible/playbooks/opnsense/manage-filter-rules.yml` required field list and normalization.
- Updates `ansible/vars/opnsense/filter-rules.yml` desired-state entries and examples.
- Updates OPNsense playbook documentation.

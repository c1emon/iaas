## Why

Most managed OPNsense filter rules do not invert source or destination matches, so requiring `source_invert` and `destination_invert` on every rule adds noise to desired state. Making these fields optional with a safe default keeps YAML shorter without changing firewall behavior.

## What Changes

- Remove `source_invert` and `destination_invert` from the required `opnsense_filter_rules` fields.
- Default omitted `source_invert` and `destination_invert` to `false` in the derived module input.
- Keep explicit `true` or `false` values supported for rules that need inverted matching.
- Update examples, current migrated rules, and documentation to omit false invert fields unless needed.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `opnsense-filter-rule-management`: Make source/destination invert fields optional in desired state with default `false` normalization before module submission.

## Impact

- Updates `ansible/playbooks/opnsense/manage-filter-rules.yml` required field list and normalization.
- Updates `ansible/vars/opnsense/filter-rules.yml` desired-state entries and examples.
- Updates OPNsense playbook documentation.

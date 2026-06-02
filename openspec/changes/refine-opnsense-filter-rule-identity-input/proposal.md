## Why

The initial filter-rule workflow requires operators to type the full `iaas:opnsense:filter:<scope>:<slug>` description for every rule. That exposes an implementation prefix, creates repetitive input, and makes identity mistakes easier in a high-risk firewall workflow.

## What Changes

- Replace user-authored full `description` identities with user-authored `scope` and `slug` fields.
- Generate each OPNsense rule `description` internally as `iaas:opnsense:filter:<scope>:<slug>` before calling `oxlorg.opnsense.rule_multi`.
- Validate `scope` and `slug` independently using lowercase letters, numbers, and hyphens.
- Preserve `description` as the immutable OPNsense identity and keep `match_fields: ['description']`.
- Prevent callers from supplying raw `description` in `opnsense_filter_rules` to avoid bypassing the generated identity model.
- Update examples and documentation to show the shorter input model.
- **BREAKING**: Existing `opnsense_filter_rules` entries that specify `description` directly must be changed to `scope` and `slug`.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `opnsense-filter-rule-management`: Refine managed filter rule identity input so operators provide `scope` and `slug`, while the workflow generates and matches on the full immutable `description`.

## Impact

- Updates `ansible/vars/opnsense/filter-rules.yml` examples and input guidance.
- Updates `ansible/playbooks/opnsense/manage-filter-rules.yml` validation and transformation before `rule_multi`.
- Updates OPNsense playbook README and management documentation.
- Changes the desired-state input contract for managed filter rules before the initial filter-rule workflow is archived.

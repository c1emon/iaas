## Context

The OPNsense rule module represents unrestricted ports as empty strings. The filter-rule playbook already builds a derived module input list, so omitted user-facing port fields can be normalized to the module-compatible empty string safely.

## Goals / Non-Goals

**Goals:**

- Allow `source_port` and `destination_port` to be omitted from `opnsense_filter_rules`.
- Normalize omitted port fields to `""` before calling `rule_multi`.
- Preserve explicit port values, aliases, and ranges.

**Non-Goals:**

- Supporting port lists in this change.
- Changing network field list support, invert defaults, identity, sequence, reload, or purge behavior.

## Decisions

### Default omitted ports in the derived apply list

The playbook will remove `source_port` and `destination_port` from required fields, then add defaults during apply-list generation.

### Keep ports as strings

Port fields remain strings because values may be empty, numeric strings, aliases, or ranges such as `21115-21117`.

## Risks / Trade-offs

- **Less explicit desired state** → Mitigated by documenting that omitted port means any port.
- **Accidental omission for restricted ports** → Operators must still declare destination/source ports when restriction is intended.

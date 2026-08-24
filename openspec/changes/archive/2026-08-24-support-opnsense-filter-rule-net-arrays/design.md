## Context

The filter-rule playbook currently passes desired rules through a derived module input list. This makes it a natural place to normalize user-friendly YAML fields into the exact parameter types expected by `oxlorg.opnsense.rule_multi`. The module expects `source_net` and `destination_net` as strings, but OPNsense often represents multiple network or interface aliases as comma-separated values.

## Goals / Non-Goals

**Goals:**

- Support YAML lists for `source_net` and `destination_net` in desired state.
- Preserve existing string support for single values and aliases.
- Convert list values to comma-separated strings in the derived apply list.
- Keep module inputs compatible with `oxlorg.opnsense.rule_multi`.

**Non-Goals:**

- Supporting list input for ports in this change.
- Changing identity, sequence, reload, purge, or credential behavior.
- Changing how OPNsense interprets aliases, CIDRs, interface identifiers, or `(self)`.

## Decisions

### Normalize only network fields

Only `source_net` and `destination_net` will accept list input. These fields commonly contain multiple logical networks and are safer to split into YAML lists for review.

`source_port` and `destination_port` will remain strings because values like `21115-21117` are ranges, not lists, and conflating range syntax with list syntax could cause incorrect firewall behavior.

### Normalize in the derived apply list

The playbook will continue to keep `opnsense_filter_rules` as user-facing input and build `opnsense_filter_rule_apply_rules` for module submission. During that transformation, list-valued network fields will be joined with commas; strings will pass through unchanged.

## Risks / Trade-offs

- **Accidental list syntax for ports remains unsupported** → Document that only net fields support arrays.
- **Mixed string/list inputs** → Normalize each field independently so existing string entries remain valid.
- **Unexpected module parameter type** → Validate with syntax/lint and keep conversion before `rule_multi`.

## Open Questions

- Should future changes support arrays for ports with explicit safeguards against range confusion?

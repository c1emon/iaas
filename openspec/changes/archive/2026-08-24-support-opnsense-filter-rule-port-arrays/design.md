## Context

The filter-rule workflow already normalizes user-friendly fields in a derived apply list before calling `oxlorg.opnsense.rule_multi`. Network fields can now be strings or lists, and port fields are optional with empty-string defaults. Port fields can use the same normalization pattern while keeping omitted ports as unrestricted.

## Goals / Non-Goals

**Goals:**

- Support YAML lists for `source_port` and `destination_port`.
- Preserve string support for single ports, aliases, ranges, and empty strings.
- Preserve omitted port fields as empty strings.
- Convert flat port lists to comma-separated strings in generated module input.

**Non-Goals:**

- Supporting nested lists or structured port objects.
- Validating whether a port string, range, or alias exists in OPNsense.
- Changing network field, identity, invert, reload, purge, or credential behavior.

## Decisions

### Normalize port fields in the derived apply list

The playbook will normalize `source_port` and `destination_port` during apply-list generation:

- omitted value → `""`
- string value → unchanged
- flat list → comma-joined string

### Keep YAML examples quoted where useful

Single numeric ports should be shown quoted, such as `"53"`, to avoid type ambiguity. Ranges and aliases may remain strings.

## Risks / Trade-offs

- **Ambiguous unquoted values** → Document quoted numeric ports in examples.
- **Nested/invalid list values** → The workflow only promises flat string-like lists; module validation remains the final schema check.
- **Hidden conversion** → Documentation states lists are normalized before module submission.

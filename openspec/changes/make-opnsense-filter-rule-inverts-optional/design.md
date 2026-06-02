## Context

The filter-rule workflow intentionally requires explicit fields for safety, but `source_invert` and `destination_invert` are almost always `false`. The `oxlorg.opnsense.rule_multi` module already supports boolean defaults, and the playbook builds a derived apply list before module submission, so optional input can be normalized safely.

## Goals / Non-Goals

**Goals:**

- Allow `source_invert` and `destination_invert` to be omitted from `opnsense_filter_rules`.
- Normalize omitted invert fields to `false` before calling `rule_multi`.
- Preserve explicit true values for inverted rules.
- Reduce desired-state noise in migrated filter rules.

**Non-Goals:**

- Making other currently required fields optional.
- Changing source/destination net semantics, identity generation, sequence, reload, or purge behavior.
- Inferring invert behavior from net value syntax.

## Decisions

### Default omitted invert fields in the derived apply list

The playbook will remove `source_invert` and `destination_invert` from `opnsense_filter_rule_required_fields`, then add defaults during apply-list generation:

```yaml
source_invert: "{{ item.source_invert | default(false) }}"
destination_invert: "{{ item.destination_invert | default(false) }}"
```

This keeps module input explicit while allowing user-facing desired state to omit false values.

### Keep explicit inverted rules supported

If a rule declares `source_invert: true` or `destination_invert: true`, the generated module input will preserve that value. This avoids changing semantics for future rules that need inverted matching.

## Risks / Trade-offs

- **Less explicit desired state** → Mitigated by defaulting only low-risk boolean fields whose safe default is `false`.
- **Accidental omission on inverted rules** → Operators must still declare `true` for inverted behavior; docs will call this out.
- **Hidden module default dependency** → The playbook normalizes defaults itself before module submission.

## Open Questions

- Should future changes make other low-risk module defaults optional after review?

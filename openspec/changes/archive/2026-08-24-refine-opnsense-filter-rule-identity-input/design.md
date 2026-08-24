## Context

The filter-rule workflow introduced by `manage-opnsense-filter-rules` uses OPNsense rule `description` as the stable identity because `oxlorg.opnsense.rule_multi` creates missing rules through `addRule`, which auto-generates UUIDs. The initial implementation asks operators to write the full identity string in each rule declaration, for example `iaas:opnsense:filter:lan:allow-dns-to-hole`.

That full string is still the correct OPNsense-side identity, but exposing the fixed prefix in the desired-state input is repetitive and increases the chance of copy/paste or format mistakes. This refinement keeps the same OPNsense matching model while making the source YAML smaller and safer to edit.

## Goals / Non-Goals

**Goals:**

- Let operators declare managed filter rule identity using `scope` and `slug` fields.
- Generate `description` internally as `iaas:opnsense:filter:<scope>:<slug>` before calling `rule_multi`.
- Keep `match_fields: ['description']` and continue treating the generated description as immutable identity.
- Validate `scope` and `slug` independently before any API write.
- Reject direct `description` input in `opnsense_filter_rules` so there is only one identity construction path.
- Update documentation and examples to use the shorter input model.

**Non-Goals:**

- Changing OPNsense-side identity away from `description`.
- Introducing UUID-based identity or raw `setRule/{uuid}` calls.
- Adding purge, authoritative reconciliation, or management of rules absent from `opnsense_filter_rules`.
- Relaxing the requirement that managed rule identities are globally unique.
- Changing rule ordering, reload behavior, credential handling, or out-of-scope firewall/NAT boundaries.

## Decisions

### Use top-level `scope` and `slug` fields

Each declared rule will provide:

```yaml
scope: lan
slug: allow-dns-to-hole
```

The playbook will derive:

```yaml
description: iaas:opnsense:filter:lan:allow-dns-to-hole
```

This keeps the YAML flat and easy to scan alongside other rule fields. `scope` should generally reflect the interface or ownership domain, while `slug` identifies the specific managed rule.

Alternative considered: nested `identity.scope` and `identity.slug`. This was rejected because existing OPNsense desired-state files use flat module-compatible dictionaries, and a nested identity object would add structure that must always be flattened before module calls.

### Transform to module-compatible rule dictionaries before apply

The playbook will keep `opnsense_filter_rules` as the user-facing variable and build a separate derived list for module input, for example `opnsense_filter_rule_apply_rules`. Each item will combine the original fields with a generated `description` field before invoking `oxlorg.opnsense.rule_multi`.

The source list must not pass directly to `rule_multi`, because `rule_multi` does not understand `scope` or `slug` as module parameters.

Alternative considered: mutate `opnsense_filter_rules` in place. This was rejected because a derived apply list makes validation and transformation responsibilities clearer.

### Validate input identity parts instead of full input description

The validation regex for both `scope` and `slug` will be:

```text
^[a-z0-9][a-z0-9-]*$
```

The workflow will still validate uniqueness after generating full descriptions. Direct `description` input will be rejected to avoid conflicting identity sources.

Alternative considered: allow either `description` or `scope`/`slug` during a transition period. This was rejected because the workflow has not been archived or populated with real managed rules yet, and a single input model is safer.

## Risks / Trade-offs

- **Breaking input shape before archive** → This change is intentionally made before the filter-rule workflow is archived or broadly used.
- **Generated field hides OPNsense description value** → Document the generated format and show examples so operators can still map YAML entries to OPNsense UI rows.
- **Non-module fields accidentally sent to `rule_multi`** → Use a derived module input list that omits `scope` and `slug` after generating `description`.
- **Duplicate generated identities** → Validate uniqueness on generated descriptions before API writes.
- **Description edits still break identity** → Treat `scope` and `slug` as immutable identity parts and document that changing either creates a different managed identity.

## Migration Plan

1. Update example rules to use `scope` and `slug` instead of full `description`.
2. Update playbook required fields from `description` to `scope` and `slug`.
3. Add validation for `scope`, `slug`, generated description uniqueness, and absence of direct `description` input.
4. Build a derived rule list with generated `description` values before `rule_multi`.
5. Re-run syntax, YAML lint, and Ansible lint validation.

Rollback is straightforward before live use: revert to full `description` input and pass `opnsense_filter_rules` directly to `rule_multi` with the original description validation.

## Open Questions

- Should future documentation recommend a fixed set of `scope` values such as interface identifiers only, or allow broader ownership domains like `floating` and `pbr`?

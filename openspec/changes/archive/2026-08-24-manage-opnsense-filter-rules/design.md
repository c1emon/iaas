## Context

The repository already uses a conservative OPNsense automation pattern: local Ansible execution, environment-provided API credentials, shared credential preflight, hand-written desired-state files, snapshot-before-write guidance, and additive writes only for explicitly declared resources. Firewall aliases, IP Alias VIPs, and PBR gateway objects follow this pattern; firewall filter rules have intentionally remained unmanaged until the rule identity and ordering model could be defined.

OPNsense 26.1.7_3 has both legacy rules and the API-backed new rules system. The `oxlorg.opnsense.rule` and `oxlorg.opnsense.rule_multi` modules target the new filter rule API (`/api/firewall/filter/*`) and Rules `[new]`, not legacy exported rules. The repository has a legacy `download_rules.csv` that is useful for migration review, but this workflow will start from hand-written desired state and will not treat the CSV as apply input.

The preferred long-term identity model is a real rule UUID, but `oxlorg.opnsense.rule_multi` creates missing rules through `addRule`, which auto-generates UUIDs. OPNsense `setRule/{uuid}` can upsert with caller-supplied UUIDs, but using that path would require raw API calls or a custom workflow. For this change, the stable identity will therefore be the rule `description`, with a strict machine-readable format.

## Goals / Non-Goals

**Goals:**

- Add a narrow workflow for OPNsense new firewall filter rules managed from `opnsense_filter_rules`.
- Use the supported `oxlorg.opnsense.rule_multi` module rather than raw API calls or a custom module.
- Manage only Rules `[new]` / API-backed filter rules, not legacy rules.
- Use `description` as immutable identity with `match_fields: ['description']`.
- Enforce the identity format `iaas:opnsense:filter:<scope>:<slug>` before any write.
- Enforce global uniqueness for managed rule descriptions.
- Use `sequence` for rule processing order and keep it separate from identity.
- Support explicit `state: present` and `state: absent` for declared rules.
- Preserve unmanaged filter rules by avoiding purge or authoritative reconciliation.
- Reuse existing credential preflight, module defaults, documentation, validation, and snapshot guidance.

**Non-Goals:**

- Managing legacy firewall rules or importing legacy CSV exports as apply input.
- Managing outbound NAT, DNAT/port-forward, source NAT, static routes, interfaces, VLANs, gateway groups, or default routing.
- Creating gateway objects referenced by rules; gateway objects remain managed by the separate gateway workflow.
- Creating caller-supplied UUID rules via `setRule/{uuid}`.
- Purging, disabling, or reconciling rules absent from `opnsense_filter_rules`.
- Implementing automatic fail-open/fail-closed behavior or state table cleanup.

## Decisions

### Use `opnsense_filter_rules` as hand-written desired state

Filter rule desired state will live in `ansible/vars/opnsense/filter-rules.yml`, parallel to existing OPNsense variables. The workflow will not generate desired state from `download_rules.csv` or files under `exports/opnsense/`.

Alternative considered: importing the current legacy rule CSV as the source of truth. This was rejected because those rules belong to the legacy rule system and because generated exports are not reviewed desired state.

### Target Rules `[new]` through `oxlorg.opnsense.rule_multi`

The playbook will use `oxlorg.opnsense.rule_multi` with `match_fields: ['description']`. This aligns with the collection's supported creation path and keeps implementation close to the existing additive Ansible pattern.

Alternative considered: raw API calls to `/api/firewall/filter/setRule/{uuid}` to get caller-supplied UUID identity. This was rejected for v1 because it would bypass the collection module and introduce a separate serialization and idempotency layer.

### Treat `description` as immutable identity

Each managed rule description must match:

```text
^iaas:opnsense:filter:[a-z0-9][a-z0-9-]*:[a-z0-9][a-z0-9-]*$
```

The structure is:

```text
iaas:opnsense:filter:<scope>:<slug>
```

Examples:

```text
iaas:opnsense:filter:lan:allow-any-ipv4
iaas:opnsense:filter:floating:allow-local-dns
iaas:opnsense:filter:opt2:reject-internal-zones
```

The description is not a human sentence and must not include labels, sequence numbers, UUID-like prefixes, or mutable rule parameters. Human-readable notes can live in comments or documentation, but not in the OPNsense description field while description is the identity.

Alternative considered: `uuid#ALLOW lan any` in description. This was rejected because the module would still match the entire description string, so changing the readable suffix would change identity.

### Keep ordering mutable and separate from identity

The playbook will require each declared rule to include `sequence`, but sequence will not appear in `match_fields`. Sequence values can be changed to reorder rules without replacing the identity.

Recommended ordering blocks will be documented, for example: low numbers for essential rules, `100-199` for selective gateway/routing-policy rules, `200-499` for special allow/block rules, and `900+` for broad default allow rules. These blocks are conventions, not marker rules; no `PBR_START` or `PBR_END` placeholder rules will be created.

Alternative considered: creating disabled marker rules as anchors. This was rejected because marker rules pollute the UI and are unnecessary when `sequence` is available.

### Validate before API writes

The playbook will fail before any OPNsense write if `opnsense_filter_rules` is missing, not a sequence, lacks required fields, contains invalid states, contains invalid identity descriptions, or has duplicate descriptions.

Alternative considered: allowing module failures to catch invalid inputs. This was rejected because the most important safety constraints are ownership and identity constraints, not just API schema validity.

### Preserve unmanaged rules

The workflow will only create, update, or delete rules explicitly listed in `opnsense_filter_rules`. It will not use `rule_multi` purge controls in this change.

Alternative considered: authoritative reconciliation for all managed-prefix rules. This was rejected for v1 because new and legacy rule interactions still need operational review, and accidental rule removal can cause lockout or traffic disruption.

## Risks / Trade-offs

- **Description edits break identity** → Use a strict machine-readable description format, validate it before writes, document immutability, and avoid natural-language descriptions.
- **Wrong sequence can shadow later rules** → Require explicit sequence and document ordering blocks; encourage snapshot and inspect review before first broad apply.
- **Gateway reference can blackhole traffic** → Keep gateway creation out of scope but document that referenced gateways must already exist and be reviewed separately.
- **Legacy and new rules may both affect traffic** → Manage only Rules `[new]`, document that legacy CSV is migration review input only, and require operators to inspect final rule order in OPNsense.
- **No purge means stale managed rules can remain if removed from YAML** → Require explicit `state: absent` for removal; defer purge to a future authoritative-management capability.
- **Module field translation issues may occur with OPNsense API changes** → Use documented validation commands and keep raw API workaround decisions out of this change unless a module bug blocks implementation.

## Migration Plan

1. Operators review existing legacy rules and decide which new filter rules to declare manually in `ansible/vars/opnsense/filter-rules.yml`.
2. Operators assign each managed rule an immutable description in `iaas:opnsense:filter:<scope>:<slug>` format.
3. Operators choose explicit sequence values using documented ordering blocks.
4. Operators run the existing OPNsense snapshot workflow before the first write.
5. Operators run syntax and lint validation for the desired-state file and playbook.
6. Operators run the filter rule playbook to create, update, or explicitly remove declared Rules `[new]` entries.
7. Operators inspect OPNsense Rules `[new]` and generated rule order, especially where legacy rules still coexist.

Rollback is manual and explicit: restore from an OPNsense snapshot/savepoint, or declare the affected managed rule with the previous desired values or `state: absent`, then re-run the workflow. Rules not listed in `opnsense_filter_rules` are not changed by this workflow.

## Open Questions

- Should a future capability validate that any `gateway` referenced by a managed filter rule exists in `opnsense_gateways` or live OPNsense state?
- Should a future capability move to caller-supplied UUID identity through `setRule/{uuid}` once the raw/API workflow is designed or upstream module support exists?
- Should a future authoritative mode purge only rules whose description starts with `iaas:opnsense:filter:` and are absent from desired state?

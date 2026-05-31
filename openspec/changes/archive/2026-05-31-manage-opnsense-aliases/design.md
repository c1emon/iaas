## Context

The repository already has an Ansible-based OPNsense management area with read-only checks, snapshots, and export workflows. OPNsense API credentials are supplied through environment variables, and existing exports identify firewall aliases as first-stage candidates for future declarative management.

This change introduces the first write-capable OPNsense workflow for firewall aliases only. The workflow must remain conservative: operators will author an explicit YAML list of aliases to create or update, and the playbook will not delete aliases that are not listed.

## Goals / Non-Goals

**Goals:**
- Provide a safe playbook for additive OPNsense alias management from a hand-written YAML file.
- Keep the desired alias data close to the Ansible OPNsense playbooks and easy to review in Git.
- Reuse the existing inventory, module defaults, and environment credential patterns.
- Batch alias operations and reload the alias target once after successful changes.
- Document the safety boundary and expected validation commands.

**Non-Goals:**
- No purge, delete, or disable behavior for aliases outside the hand-written YAML source.
- No automatic alias type migration by delete/recreate.
- No management of firewall rules, NAT, interfaces, DHCP, Unbound, or other OPNsense areas.
- No automatic conversion of exported aliases into desired-state input.

## Decisions

### Use a hand-written YAML source file

Store desired aliases in a repository YAML file rather than deriving them directly from `exports/opnsense/firewall-aliases.json`.

Rationale: exports are observations from a live firewall, while desired-state files are reviewed intent. Keeping them separate avoids accidentally re-applying every exported alias or treating observed state as policy.

Alternative considered: generate desired aliases from export output. This is useful later as a migration helper, but it creates more review and normalization complexity than the first write-capable workflow needs.

### Use additive alias management only

The playbook will create or update aliases listed in the YAML source and leave all other aliases untouched.

Rationale: OPNsense aliases may be manually maintained or referenced by firewall rules outside this repository. Additive behavior provides a safer first step before any namespace ownership or purge semantics are introduced.

Alternative considered: use `alias_multi` purge behavior. This was rejected for the first version because a wrong source list could remove aliases used by active firewall policy.

### Use `oxlorg.opnsense.alias_multi` with one alias reload

Use the collection's bulk alias module for the desired list and call the alias reload target once after successful changes.

Rationale: bulk operations are simpler and faster than looping over individual alias tasks, and a single reload avoids repeated reloads during a batch.

Alternative considered: loop over `oxlorg.opnsense.alias`. This is easier to debug item-by-item but creates more task noise and reload coordination.

### Do not automatically handle alias type changes

If an existing alias has a different type than the desired definition, the workflow should not silently delete and recreate it.

Rationale: deleting an alias may affect rules or services that reference it. Type migration should be an explicit operator action after review.

Alternative considered: automatically recreate aliases whose type differs. This was rejected due to safety risk.

## Risks / Trade-offs

- Alias type drift → Mitigation: document that type changes are not automatically migrated and require manual handling.
- Desired YAML contains invalid content for an alias type → Mitigation: rely on Ansible/module validation and provide syntax/lint validation commands.
- Operator expects full reconciliation → Mitigation: name and document the workflow as additive only; explicitly state that unlisted aliases are untouched.
- Alias reload activates unintended updates → Mitigation: batch only the reviewed YAML source and keep scope limited to aliases.

## Migration Plan

1. Add the desired alias YAML source with a small reviewed initial set.
2. Run existing readonly/snapshot workflows before the first write run.
3. Run syntax and lint validation locally.
4. Apply the alias playbook with valid OPNsense API credentials.
5. Use existing export or read-only listing workflows to verify the resulting aliases.

Rollback is manual for this first version: because the workflow is additive and does not purge unlisted aliases, reverting a mistaken content update requires restoring the previous alias definition in YAML and re-running the playbook, or correcting it directly in OPNsense.

## Open Questions

- Which initial aliases should be included in the first desired YAML source file?
- Should a future change introduce a managed prefix or namespace to support safe purge behavior for repository-owned aliases?

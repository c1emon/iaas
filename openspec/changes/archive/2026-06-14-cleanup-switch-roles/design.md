## Context

The repository now uses `c1emon.xikeos` as the source of truth for XikeOS switch
terminal behavior, facts collection, resource schemas, check-mode previews,
apply behavior, and lifecycle results. Earlier repository-local SKS8300 profile
parsers, command planners, resource adapters, and intent translation have been
removed or deprecated.

Two switch roles remain:

- `switch_readonly_facts`: validates runtime inputs, maps gather variables, calls
  `c1emon.xikeos.xikeos_facts`, and exposes collection-native facts.
- `switch_config`: validates collection-native resources, applies repository
  policy, calls lifecycle-complete resource modules in static order, gates live
  apply, checks command output, and aggregates a report.

This change decides which role boundaries still provide value and removes or
renames role layers that only hide direct collection usage.

## Goals / Non-Goals

**Goals:**

- Make switch role boundaries explicit: roles may enforce repository policy, but
  SHALL NOT implement platform parsing, resource schemas, diff planning, or
  command rendering.
- Remove `switch_readonly_facts` if it has become a thin wrapper around a single
  collection facts call and move its validation/export coordination to the
  read-only playbook.
- Keep or simplify `switch_config` only if it remains a useful safety
  orchestrator around multiple resource modules and project-specific policy.
- Update docs, tests, and specs so operators can tell when to call collection
  modules directly and when to use repository orchestration.

**Non-Goals:**

- Modify the `c1emon.xikeos` collection.
- Reintroduce local SKS8300 parsers, resource adapters, or command planners.
- Change inventory credentials or live switch configuration semantics.
- Add new switch resources beyond the lifecycle-complete modules already used.

## Decisions

### Inline read-only facts role if no reusable policy remains

`switch_readonly_facts` should be removed or reduced to zero if implementation
confirms it only wraps `c1emon.xikeos.xikeos_facts`. The read-only playbook can
own runtime validation, gather variables, collection invocation, and export task
inclusion directly.

Rationale: a role that only calls one collection module makes the workflow harder
to read and creates maintenance burden without adding safety policy.

Alternative considered: keep the role for consistency. Rejected unless the role
contains reusable policy not better expressed in the playbook.

### Keep configuration orchestration only if it adds safety policy

`switch_config` may remain because it coordinates multiple lifecycle resource
modules and enforces repository-specific safety controls. If kept, its README
and tests must describe it as a safety/orchestration role, not an XikeOS
implementation layer.

Rationale: static resource ordering, apply gating, allowed-state policy,
destructive-command checks, and report aggregation are repository concerns that
do not belong inside the collection.

Alternative considered: inline all configuration tasks into `config-plan.yml`.
This is acceptable if implementation shows the role has no reuse value, but it
may make the playbook long and reduce readability.

### Keep export caller-owned

Switch facts export should remain playbook-owned regardless of whether the facts
role is removed. Roles should not write files or create export directories as a
side effect of collecting facts.

Rationale: export paths and formats are environment/workflow choices, while
facts collection should remain side-effect-free.

## Risks / Trade-offs

- Removing a role may break direct role callers → Document migration to the
  playbook or collection module call.
- Inlining validation may duplicate a few checks in playbooks → Accept if it
  removes a redundant abstraction.
- Keeping `switch_config` may preserve some wrapper code → Accept only while it
  clearly enforces repository safety policy.
- Docs may drift between role README and playbook README → Delete role README
  when deleting a role, and centralize usage in `ansible/README.md` and
  `ansible/playbooks/switches/README.md`.

## Migration Plan

1. Audit role callers and references.
2. Inline or remove `switch_readonly_facts` if it is only a collection wrapper.
3. Preserve read-only export behavior at playbook scope.
4. Review `switch_config` and either keep it as a safety orchestration role or
   inline it into `config-plan.yml` if the role adds no reusable policy.
5. Update tests and docs to match the final boundary.
6. Run unit tests, compile checks, YAML lint, Ansible syntax checks, and safe
   switch check-mode preview.

Rollback is to restore the removed role tasks and playbook role invocation from
version control.

## Open Questions

- Should `switch_config` be renamed in a follow-up to make its policy role more
  explicit, such as `switch_config_orchestrator`?
- Are there external direct callers of `switch_readonly_facts`, or is the
  repository playbook the only supported entrypoint?

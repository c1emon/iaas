## Context

The SKS8300 automation work is moving from a read-only facts playbook toward a platform adapter for the SKS8300 switch family. Read-only facts should remain safe and subset-driven, while future configuration changes need a stronger lifecycle and safety model than raw CLI commands.

MikroTik/RouterOS Ansible modules provide a useful reference: raw command modules are separate from declarative resource modification, resource schemas describe primary keys and fields, and idempotent modification follows fetch, match, diff, apply, and verify phases. The SKS8300 design should borrow those patterns while continuing to use SSH `network_cli` and the local Python profile core.

## Goals / Non-Goals

**Goals:**

- Define a separate `switch_config` workflow for SKS8300-series configuration resources.
- Manage configuration through declarative intent rather than user-supplied CLI command lists.
- Require plan/diff behavior before apply and make apply opt-in.
- Reuse SKS8300 profile parsing and command catalog facilities created for read-only facts.
- Establish a resource registry pattern for fields, primary keys, desired state, diff, command rendering, and verification.
- Start with a narrow future resource scope such as VLANs and interface VLAN membership.

**Non-Goals:**

- Do not implement configuration mutation as part of the read-only facts role.
- Do not provide a raw arbitrary config command runner as the primary interface.
- Do not attempt full switch feature coverage in the first config framework.
- Do not publish a standalone Ansible collection in this change.
- Do not bypass explicit apply confirmation for live changes.

## Decisions

### Separate read-only and configuration roles

Configuration changes should live in a future `switch_config` role rather than being added as a mode to `switch_readonly_facts`.

Target task layout:

```text
roles/switch_config/tasks/
  main.yml
  validate.yml
  collect_current.yml
  plan.yml
  diff.yml
  apply.yml
  verify.yml
  export.yml
```

This keeps read-only facts safe by default and lets configuration tasks have stronger guardrails, reporting, and explicit apply behavior.

Alternative considered: add `switch_mode: facts|config` to one role. Rejected because the two workflows have different safety, validation, and failure semantics.

### Use declarative intent, not raw config commands

Operators should declare desired resources:

```yaml
switch_platform_profile: sks8300
switch_config_apply: false
switch_config_intent:
  vlans:
    - id: 10
      name: users
      state: present
  interfaces:
    ethernet1/0/1:
      mode: access
      access_vlan: 10
```

The profile core computes the needed operations and renders candidate CLI commands internally.

Alternative considered: accept `switch_config_commands`. Rejected because arbitrary commands make idempotency, diff, rollback, audit, and safety validation weak.

### Resource registry inspired by MikroTik `api_modify`

The SKS8300 profile should contain a resource registry that declares resource identity and field behavior. A resource definition can include:

- primary keys or resource identity fields
- supported fields and defaults
- read-only/write-only/sensitive markers
- desired state choices such as `present` and `absent`
- current-state collection commands
- diff function
- render function
- verify function
- operation risk level

This becomes the source of truth for config planning and prevents field behavior from being hard-coded independently in tasks.

Alternative considered: one-off YAML tasks per resource. Rejected because resource behavior would fragment as soon as VLANs, interface modes, trunks, LAGs, or STP are added.

### Fixed lifecycle: collect, parse, validate, diff, render, apply, verify

The workflow should always collect current state and produce a plan before apply. Apply should run only when `switch_config_apply: true` is set, and generated commands should still pass safety validation.

This supports check-mode-like behavior even before a custom module exists and keeps the default operator experience non-mutating.

Alternative considered: render and apply directly from intent. Rejected because it would not prove idempotency or show a meaningful diff before mutation.

### Reuse shared profile core, not read-only role internals

The future config workflow should use shared SKS8300 modules under `ansible/module_utils/switch_profiles/sks8300/`, including parsers and command metadata. It should not import role task variables or depend on read-only role internals.

Alternative considered: have config role call read-only role tasks as a subroutine. Rejected because it creates hidden coupling between independent workflows.

## Risks / Trade-offs

- CLI-based config idempotency can be fragile when device output format changes → Keep resource scope narrow and verify after apply.
- Declarative resource registry takes more upfront design than raw commands → Start with VLANs/interfaces where current facts already parse useful state.
- Applying config over `network_cli` can fail mid-sequence → Require explicit apply, export command plan, and verify post-state; defer rollback automation until behavior is understood.
- Inventory/operator mistakes can cause disruptive changes → Validate intent, require allowed operations, and default to plan/diff only.
- Future resource schemas may evolve → Keep field metadata centralized and document compatibility expectations.

## Migration Plan

1. Finish the profile-driven read-only facts change first so current-state parsing and command catalog are reusable.
2. Add a `switch_config` role scaffold with safe defaults and no apply-by-default behavior.
3. Add SKS8300 resource registry structures for an initial narrow resource scope.
4. Implement current-state collection through profile read commands and existing parsers.
5. Implement diff and command rendering for the first resource set.
6. Add explicit apply and verification phases.
7. Validate with check/diff first, then a controlled live apply on low-risk resources.

Rollback for a failed implementation is to remove the `switch_config` role and leave read-only facts unaffected. Runtime rollback for device changes should initially be manual or plan-based until the resource framework proves reliable.

## Open Questions

- Which first resource should be implemented: VLAN definitions only, interface access VLAN, or both together?
- Should generated config commands be saved as a pending plan artifact requiring manual confirmation before a second apply run?
- Should rollback command generation be part of the first implementation or deferred until after diff/apply/verify is stable?

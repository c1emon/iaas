## Context

The repository's switch configuration workflow has been migrated to `c1emon.xikeos` v0.2.x as the primary automation surface. The collection already provides `xikeos_facts`, collection-native `ansible_network_resources`, and lifecycle resource modules for VLANs, base interfaces, L2 interfaces, L3 interfaces, LAG interfaces, static routes, and ACLs.

The current repository implementation still contains a local `xikeos_resources.py` helper that defines resource schemas, validates fields, computes a cross-resource diff, maps repository intent to collection module arguments, and verifies resulting state. That helper duplicates collection behavior and keeps XikeOS resource adaptation in this repository. Recent exploration also removed SKS8300 profile selection, reinforcing that model/firmware adaptation belongs in the collection rather than in caller-owned variables or local parsers.

## Goals / Non-Goals

**Goals:**

- Make switch configuration inputs collection-native: each resource entry supplies the `state` and `config` shape accepted by the corresponding `c1emon.xikeos` resource module.
- Remove repository-local resource schemas, field normalization, diff generation, rendered command synthesis, and post-state verification from `xikeos_resources.py`.
- Keep repository-owned safety and workflow controls: explicit `switch_config_apply`, allowed-state policy, static module ordering, no raw arbitrary command input, and aggregated reports.
- Let collection modules own argspec validation, check-mode previews, command generation, before/after state, apply, and verification through their lifecycle framework.
- Keep read-only facts collection on `c1emon.xikeos.xikeos_facts` and continue treating `ansible_network_resources` as authoritative state.

**Non-Goals:**

- Modify or publish the upstream `c1emon.xikeos` collection.
- Introduce a new `c1emon.xikeos.xikeos_config_intent` collection module.
- Reintroduce SKS8300 profile selection, local CLI parsers, or command-plan based switch facts.
- Support raw arbitrary configuration command lists as a primary interface.
- Preserve compatibility with the old repository-specific `switch_config_intent` field aliases such as `id`, `present`/`absent`, `tagged_vlans`, or `untagged_vlans`.

## Decisions

### Use collection-native grouped resource calls

Configuration variables should describe module calls, not a repository-specific intent model. The preferred shape is a grouped mapping where each supported resource contains a list of calls:

```yaml
switch_config_resources:
  vlans:
    - state: merged
      config:
        - vlan_id: 3999
          name: ansible-test
    - state: deleted
      config:
        - vlan_id: 3998
  l2_interfaces:
    - state: merged
      config:
        - name: Ethernet1/0/48
          mode: access
          access_vlan: 3999
```

Rationale: this keeps operator input close to the collection module API while still allowing the role to aggregate related switch configuration in one vars file.

Alternative considered: separate variables such as `switch_config_vlans` and `switch_config_l2_interfaces`. Rejected as the primary interface because it scatters resource configuration and makes reporting less uniform, though implementation may internally normalize to per-resource call lists.

Alternative considered: retain `switch_config_intent` and translate it. Rejected because translation preserves the local resource model that this change is meant to remove.

### Use static module dispatch rather than dynamic module names

The role should explicitly call each supported module in a known order instead of constructing module names dynamically. Static dispatch keeps Ansible syntax checkable, makes no-op resources obvious, and avoids hidden runtime module resolution errors.

Recommended order:

1. `c1emon.xikeos.xikeos_vlans`
2. `c1emon.xikeos.xikeos_interfaces`
3. `c1emon.xikeos.xikeos_lag_interfaces`
4. `c1emon.xikeos.xikeos_l2_interfaces`
5. `c1emon.xikeos.xikeos_l3_interfaces`
6. `c1emon.xikeos.xikeos_static_routes`
7. `c1emon.xikeos.xikeos_acls`

Rationale: static ordering preserves the repository's orchestration role without requiring it to understand device-specific internals. VLANs and base interfaces run before dependent L2/L3/routing resources.

### Replace allowed operations with allowed states

The current `switch_config_allowed_operations` policy is based on repository-computed operations (`create`, `update`, `remove`, `no-op`). Once collection modules own diffing, the repository should gate module `state` values instead:

```yaml
switch_config_allowed_states:
  - merged
```

Operators can opt into broader behavior by adding `replaced` or `deleted` explicitly.

Rationale: module states are the collection-native safety boundary. The repository cannot reliably know create/update/remove without reimplementing collection diff logic.

Alternative considered: continue computing create/update/remove in the repository. Rejected because it duplicates collection lifecycle behavior.

### Use check mode as the normal planning surface

Plan-only runs should invoke the same resource modules in check mode and aggregate their returned `changed`, `commands`, `before`, and `after` fields. Apply runs should invoke the same modules without check mode only when `switch_config_apply: true`.

Rationale: collection modules already own diff and command generation. Check mode is the most faithful preview of what apply would do.

Alternative considered: call `state=rendered` for planning. Rejected as the default because rendered output does not necessarily include gathered current state or idempotent diff behavior.

### Keep reports as repository-owned aggregation

The repository should continue exporting a change report, but its inputs should be module results rather than local planner output. Reports should include requested resources, allowed-state policy, apply status, preview/apply module results, and command summaries while avoiding plaintext secrets.

Rationale: audit/report shape is project-specific even though resource lifecycle belongs to the collection.

## Risks / Trade-offs

- Existing example vars use `switch_config_intent` and repository field aliases → Migration requires rewriting examples to collection-native resource module fields.
- Collection module schemas may be less ergonomic than the old local aliases → Accept this trade-off to avoid schema drift and keep the collection authoritative.
- Dynamic call list looping is limited by Ansible module syntax → Use static task blocks per resource instead of dynamic module FQCN construction.
- Syntax checks still require the `c1emon.xikeos` collection installed locally → Keep unit tests for variable normalization/policy where possible and document collection installation before Ansible syntax checks.
- Removing repository verification may feel like less safety → Collection modules return `before`/`after` and can gather after apply; repository reports should surface those results rather than duplicate verification.

## Migration Plan

1. Introduce `switch_config_resources` and `switch_config_allowed_states` defaults.
2. Update switch vars examples from repository-specific `switch_config_intent` to collection-native grouped resource calls.
3. Refactor validation to reject `switch_config_intent`, raw command lists, unknown resource keys, unknown states, and states outside `switch_config_allowed_states`.
4. Remove current-state collection, local planning, local diff, local verification, and Python filter/helper usage from `switch_config` role.
5. Replace preview/apply tasks with static collection module calls using check mode for plan-only runs and normal execution only when `switch_config_apply: true`.
6. Aggregate module preview/apply results into the existing change report format.
7. Delete `ansible/module_utils/xikeos_resources.py` and `ansible/filter_plugins/switch_profiles.py` when no longer referenced.
8. Update docs and tests to assert collection-native resource variable shape and repository policy gates.

Rollback is to restore the prior repository-local planner and `switch_config_intent` shape from version control. Because this repository is test-only and configuration apply remains opt-in, no data migration is required.

## Open Questions

- Should the default allowed states include only `merged`, or should `deleted` be allowed when explicitly present in examples for VLAN cleanup?
- Should plan-only runs use only check mode, or also collect `xikeos_facts` for a separate pre-change snapshot in the report?
- Should unsupported rendered-only resources be rejected by resource-key validation, or simply omitted from supported `switch_config_resources` keys and left to separate playbooks?

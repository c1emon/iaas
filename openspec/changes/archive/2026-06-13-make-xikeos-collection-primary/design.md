## Context

The switch automation code was originally built before the XikeOS collection had a complete native facts and resource lifecycle surface. The repository therefore owns SKS8300 command catalogs, local parsers, a repository-specific `switch_facts` schema, raw command export planning, and a limited VLAN/L2 configuration mapper.

`c1emon.xikeos` v0.2.0 changes that balance. It provides `xikeos_facts`, standard `ansible_net_*` facts, `ansible_network_resources`, mutating-command guards in `xikeos_command`, redaction, and lifecycle-complete resource modules for VLANs, base interfaces, L2 interfaces, L3 interfaces, LAG interfaces, static routes, and ACLs. This repository has no production consumers, so preserving the old `switch_facts` schema would add complexity without value.

## Goals / Non-Goals

**Goals:**

- Use `c1emon.xikeos` v0.2.x as the required switch automation baseline.
- Make `xikeos_facts` the normal read-only facts collection path.
- Make `ansible_net_*` and `ansible_network_resources` the canonical switch state schema.
- Remove normal workflow dependence on SKS8300 local command planning and parsing.
- Expand declarative configuration coverage to collection lifecycle resources: VLANs, base interfaces, L2 interfaces, L3 interfaces, LAGs, static routes, and ACLs.
- Preserve repository-level safety controls: explicit apply opt-in, allowed-operation policy, destructive command blocking, redacted reports, and no arbitrary raw command-list interface.
- Keep smoke/debug command execution separate from normal facts and configuration workflows.

**Non-Goals:**

- Preserve compatibility with old `switch_facts` fields or export filenames.
- Preserve SKS8300 command IDs, local parser behavior, or raw command export plans as a stable API.
- Add lifecycle apply support for collection modules that are rendered-only in v0.2.0, such as STP, ERPS, EAPS, mirror, QinQ, port isolation, flex monitor link, or OSPF v2.
- Make `xikeos_config` the default apply engine.
- Modify or publish the upstream `c1emon.xikeos` collection.

## Decisions

### Adopt collection-native facts as the only canonical facts schema

The read-only facts workflow should call `c1emon.xikeos.xikeos_facts` and expose the resulting `ansible_net_*` values and `ansible_network_resources` directly. The workflow should not adapt these results back into the old repository-specific `switch_facts` schema.

Rationale: the project is test-only, so a compatibility adapter would keep two schemas alive without protecting real consumers. The collection-native schema is richer and aligns future resource work with Ansible network conventions.

Alternative considered: expose both `switch_facts` and `switch_native_facts`. Rejected because it preserves migration complexity the project does not need.

### Treat local SKS8300 parser/profile code as removable implementation debt

The normal facts path should not depend on local SKS8300 parser/profile filters. Implementation may delete them if they become unused or keep narrowly scoped smoke/debug helpers if that is simpler during migration.

Rationale: the old local parser stack exists to compensate for missing collection capabilities. Once `xikeos_facts` is primary, retaining local parsing as normal behavior undermines the schema reset.

Alternative considered: keep local parsers as supplemental fact providers for missing fields such as BootRom or MAC addresses. Rejected for this change because those fields are not required in the new canonical schema.

### Use lifecycle-complete collection resource modules for configuration

The configuration workflow should model desired state using collection resource schemas and invoke lifecycle-complete modules for supported resources:

- `c1emon.xikeos.xikeos_vlans`
- `c1emon.xikeos.xikeos_interfaces`
- `c1emon.xikeos.xikeos_l2_interfaces`
- `c1emon.xikeos.xikeos_l3_interfaces`
- `c1emon.xikeos.xikeos_lag_interfaces`
- `c1emon.xikeos.xikeos_static_routes`
- `c1emon.xikeos.xikeos_acls`

Planning should prefer `rendered`, `gathered`, check mode, module `commands`, `before`, and `after` results over repository-rendered command strings. Verification should compare desired state against `ansible_network_resources` or module after-state.

Rationale: resource modules now provide lifecycle behavior and device parsing that the repository should not duplicate.

Alternative considered: keep the current local diff/renderer and only add more mapping targets. Rejected because it keeps the repository as a parallel lifecycle engine.

### Keep repository safety and reporting above the collection

Even though collection modules perform mutation, the repository should still own when they are called. The default configuration path remains plan-only. Apply requires explicit opt-in, allowed-operation policy still gates resources, and rendered/module command output still undergoes destructive-pattern checks before mutation.

Rationale: collection modules improve idempotency and parsing, but the repository workflow still expresses operator intent, apply gates, and audit/report expectations.

Alternative considered: tell operators to call collection modules directly. Rejected because it removes useful orchestration and audit behavior already present in the repository.

### Keep raw command execution out of normal workflows

`xikeos_command` should remain available for smoke tests and debugging, but normal facts collection should use `xikeos_facts` and normal configuration should use lifecycle resource modules. `xikeos_config` should remain a documented fallback for unsupported gaps only.

Rationale: v0.2.0 blocks mutating command prefixes by default, but raw commands still provide weaker state semantics than facts and resource modules.

Alternative considered: use `xikeos_command` to gather old raw outputs and parse locally. Rejected because it preserves the old model.

## Risks / Trade-offs

- Existing docs/tests/export files reference `switch_facts` → Rewrite or delete them during implementation.
- Collection parser behavior may not match all observed SKS8300 firmware output → Validate with smoke runs and keep failures explicit rather than silently falling back to old schema.
- Some old fields disappear from normal exports → Accept the loss because `ansible_network_resources` is the new canonical schema.
- Collection redaction may differ from local redaction → Treat collection redaction as the normal behavior and add repository report redaction checks for exported artifacts.
- Lifecycle modules may not support every resource mode or operation → Limit apply support to lifecycle-complete modules and fail clearly for unsupported or rendered-only resources.
- `ansible_network_resources` is controlled by the collection and may evolve → Constrain `c1emon.xikeos` to v0.2.x for this change.

## Migration Plan

1. Constrain `c1emon.xikeos` to v0.2.x in collection requirements and update setup documentation.
2. Replace read-only facts role internals with `xikeos_facts` collection calls and native fact outputs.
3. Rewrite export tasks and documentation around `ansible_net_*` and `ansible_network_resources`.
4. Refactor configuration planning to gather current state from collection facts/resource modules.
5. Expand config resource handling to lifecycle-complete collection modules for VLANs, interfaces, L2, L3, LAG, static routes, and ACLs.
6. Remove or isolate unused SKS8300 parser/profile/filter code and update tests accordingly.
7. Run lint, unit tests, and safe switch smoke/check-mode playbooks.

Rollback within the test project is to revert this change and restore the archived local parser/schema workflow. No production data migration is required.

## Open Questions

- Should the read-only facts export write the full Ansible facts object or only selected `ansible_net_*` plus `ansible_network_resources` keys?
- Should config intent mirror collection module schemas exactly, or keep a thin repository wrapper for allowed-operation policy and defaults?
- Which live-device smoke commands are acceptable to validate `xikeos_facts` coverage on the current SKS8300 firmware?

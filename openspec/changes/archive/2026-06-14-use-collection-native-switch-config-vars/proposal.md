## Why

The switch configuration role still carries a repository-local `xikeos_resources.py` planner that duplicates XikeOS collection resource schemas, diffing, command summaries, and verification even though `c1emon.xikeos` v0.2.x already provides facts plus lifecycle resource modules. This creates schema drift risk and keeps device/resource adaptation in this repository instead of inside the collection.

## What Changes

- **BREAKING**: Replace repository-specific `switch_config_intent` with collection-native per-resource configuration variables that map directly to `c1emon.xikeos` resource module `config` and `state` inputs.
- **BREAKING**: Remove the repository-local `xikeos_resources.py` planner/filter path; collection modules become the only source for resource schema validation, diff/check-mode behavior, command generation, apply, and after-state.
- Refactor `switch_config` role tasks to call lifecycle-complete collection modules directly for VLANs, base interfaces, L2 interfaces, L3 interfaces, LAG interfaces, static routes, and ACLs.
- Keep repository-level orchestration only where it adds project policy: explicit apply gate, allowed-state policy, module ordering, no raw arbitrary command interface, result aggregation, and redacted reporting.
- Update switch configuration examples and documentation to use collection-native resource module shapes rather than repository-translated fields such as `present`/`absent`, `id`, `tagged_vlans`, or `untagged_vlans` where collection modules expect different names.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `sks8300-config-resource-framework`: Replace repository-owned intent planning/diffing with direct collection-native resource module orchestration and allowed-state policy.
- `xikeos-network-resources-primary`: Clarify that switch configuration inputs use collection-native resource module schemas and that repository workflows do not maintain parallel resource definitions.
- `xikeos-collection-switch-automation`: Clarify repository preference for direct `c1emon.xikeos` resource modules over local adapters when collection modules provide lifecycle behavior.
- `sks8300-profile-readonly-facts`: Supplemental archive sync cleaned up facts-side requirements to reflect collection-native facts instead of SKS8300 profile command planning.
- `switch-cli-readonly-facts`: Supplemental archive sync aligned read-only switch requirements with native XikeOS facts and removed obsolete profile-parser assumptions.
- `switch-readonly-facts-export-workflow`: Supplemental archive sync aligned export requirements with collection-native facts and removed normal-workflow raw profile export assumptions.

## Impact

- Affected Ansible role: `ansible/roles/switch_config/` validation, planning, preview/apply, verification, export, defaults, and README.
- Affected playbooks and vars: `ansible/playbooks/switches/config-plan.yml`, switch example vars under `ansible/vars/switches/`, and switch playbook documentation.
- Affected Python support code: remove `ansible/module_utils/xikeos_resources.py` and the associated `ansible/filter_plugins/switch_profiles.py` facade if no longer needed.
- Affected tests: update migration/unit tests that currently import or assert the repository-local planner, and add tests that assert direct collection-native variable routing and policy checks.
- Dependency impact: no new collection dependency; this change relies on the existing `c1emon.xikeos` v0.2.x baseline.

## Archive Notes

- Review after implementation found that facts-side main specs were also updated
  while archiving prior XikeOS collection migration work. This archive records
  those supplemental spec-sync updates so future readers do not need to infer
  them from main spec diffs alone.
- `ansible/module_utils/xikeos_resources.py` was already absent from committed
  history by the time this archive was reviewed; task 4.1 represents confirming
  no role task imports or depends on that local planner path.

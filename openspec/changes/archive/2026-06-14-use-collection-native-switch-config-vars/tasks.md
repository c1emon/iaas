## 1. Variable Contract and Documentation

- [x] 1.1 Replace `switch_config_intent` defaults with `switch_config_resources` and `switch_config_allowed_states` defaults.
- [x] 1.2 Update switch configuration example vars to use collection-native grouped resource calls with `state` and `config` fields.
- [x] 1.3 Update switch playbook and role documentation to explain collection-native resource inputs, allowed states, and apply behavior.
- [x] 1.4 Document migration from legacy repository-specific fields such as `id`, `present`/`absent`, `tagged_vlans`, and `untagged_vlans` to collection module schemas.

## 2. Role Workflow Simplification

- [x] 2.1 Refactor validation to reject `switch_config_intent`, raw command lists, unknown resource keys, missing `state`/`config`, and states outside `switch_config_allowed_states`.
- [x] 2.2 Remove current-state collection and local planning tasks from the configuration workflow.
- [x] 2.3 Replace preview/diff behavior with direct static calls to lifecycle-complete `c1emon.xikeos` resource modules in check mode.
- [x] 2.4 Replace apply behavior with the same static collection module calls gated by `switch_config_apply: true`.
- [x] 2.5 Preserve deterministic module ordering for VLANs, base interfaces, LAG interfaces, L2 interfaces, L3 interfaces, static routes, and ACLs.
- [x] 2.6 Preserve command-output safety checks against collection module results before live apply is considered successful.

## 3. Report Aggregation

- [x] 3.1 Rewrite `switch_config_change_report` to summarize requested collection-native resources, allowed-state policy, preview results, apply results, and apply status.
- [x] 3.2 Remove report fields that depend on repository-local diff/rendered command planning.
- [x] 3.3 Ensure report and debug output avoid plaintext secrets and keep module results under `no_log` where needed.

## 4. Python Helper Removal

- [x] 4.1 Confirm `ansible/module_utils/xikeos_resources.py` is absent after role tasks no longer import it.
- [x] 4.2 Remove `ansible/filter_plugins/switch_profiles.py` after role tasks no longer use planner filters.
- [x] 4.3 Update tests that currently import `xikeos_resources.py` to assert role variable validation, collection-native routing, and policy behavior instead.

## 5. Verification

- [x] 5.1 Run Python unit tests for updated Ansible support code.
- [x] 5.2 Run `python -m compileall` for remaining Ansible Python files.
- [x] 5.3 Run YAML lint on changed playbooks, role defaults, role tasks, vars, and OpenSpec artifacts.
- [x] 5.4 Run Ansible syntax checks in an environment where `c1emon.xikeos` is installed.
- [x] 5.5 Run safe switch check-mode preview workflows with live device credentials when available.

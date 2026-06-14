## 1. Audit and Boundary Decision

- [x] 1.1 Search for all references to `switch_readonly_facts`, `switch_config`, and switch role output variables.
- [x] 1.2 Confirm whether `switch_readonly_facts` has any supported direct role callers beyond `playbooks/switches/readonly-facts.yml`.
- [x] 1.3 Decide whether to remove `switch_readonly_facts` completely or keep a documented compatibility shim.
- [x] 1.4 Decide whether `switch_config` remains a role or should be inlined into `playbooks/switches/config-plan.yml`.

## 2. Read-only Facts Cleanup

- [x] 2.1 Inline runtime validation, gather subset variables, and `c1emon.xikeos.xikeos_facts` invocation into `playbooks/switches/readonly-facts.yml` if the role is removed.
- [x] 2.2 Preserve existing playbook-owned facts export behavior and output variable names used by `tasks/export-readonly-facts.yml`.
- [x] 2.3 Remove `ansible/roles/switch_readonly_facts/` if no compatibility shim is retained.
- [x] 2.4 Update switch read-only documentation to describe the playbook as the supported entrypoint and direct collection usage as the fallback for custom callers.

## 3. Configuration Role Cleanup

- [x] 3.1 If `switch_config` remains, update its README and task names to emphasize safety orchestration rather than platform/resource implementation.
- [x] 3.2 If `switch_config` is inlined, move validation, static module order, apply gate, destructive-command checks, and report aggregation into `config-plan.yml` or imported playbook tasks.
- [x] 3.3 Ensure collection-native `state` and `config` inputs remain unchanged for all supported resource groups.
- [x] 3.4 Ensure default non-mutating behavior, `switch_config_apply`, and `switch_config_allowed_states` behavior remain unchanged.

## 4. Tests and Documentation

- [x] 4.1 Update `ansible/tests/test_xikeos_migration.py` to assert the chosen role boundary and absence of repository-local platform/resource implementations.
- [x] 4.2 Update `ansible/README.md` and `ansible/playbooks/switches/README.md` for the final read-only and configuration entrypoints.
- [x] 4.3 Remove or update obsolete role READMEs for any deleted roles.
- [x] 4.4 Update migration notes for direct callers if role entrypoints are removed.

## 5. Verification

- [x] 5.1 Run Python unit tests for updated Ansible workflow assertions.
- [x] 5.2 Run `python -m compileall` for remaining Ansible Python files.
- [x] 5.3 Run YAML lint on changed playbooks, role tasks, vars, and OpenSpec artifacts.
- [x] 5.4 Run Ansible syntax checks for `readonly-facts.yml` and `config-plan.yml` with `c1emon.xikeos` installed.
- [x] 5.5 Run safe switch check-mode preview workflows against `sw-core` when credentials are available.

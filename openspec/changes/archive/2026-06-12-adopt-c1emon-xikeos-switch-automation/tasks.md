## 1. Dependency and Inventory Setup

- [x] 1.1 Add `c1emon.xikeos` to `ansible/requirements.yml` alongside existing collection dependencies.
- [x] 1.2 Document repository collection installation with `uv run ansible-galaxy collection install -r ansible/requirements.yml` and note the underlying Galaxy collection name.
- [x] 1.3 Document required Python parser packages for collection-backed facts/resources, including `ttp` and `textfsm` where applicable.
- [x] 1.4 Change switch inventory/group variables to use `ansible_network_os: c1emon.xikeos.xikeos` while preserving `ansible.netcommon.network_cli` and SSH credential variables.

## 2. Read-only Switch Workflow Migration

- [x] 2.1 Add or update a non-mutating connectivity/smoke path that runs a safe command through `c1emon.xikeos.xikeos_command`.
- [x] 2.2 Update the read-only facts workflow to use native XikeOS collection command or gathered-resource operations where they provide equivalent data.
- [x] 2.3 Preserve existing `switch_facts` output shape by adapting collection output or retaining compatibility parsing where needed.
- [x] 2.4 Ensure read-only collection never enters configuration mode and still blocks mutating command prefixes.
- [x] 2.5 Preserve caller-owned YAML/JSON/raw export behavior and redaction for any raw running configuration output.

## 3. Declarative Configuration Workflow Migration

- [x] 3.1 Map existing VLAN intent fields and states to `c1emon.xikeos.xikeos_vlans` behavior, including gathered/check-mode outputs.
- [x] 3.2 Map supported interface intent to appropriate `c1emon.xikeos` interface resource modules or identify unsupported gaps.
- [x] 3.3 Route supported VLAN/interface mutation through lifecycle-safe collection modules behind the existing `switch_config_apply` gate.
- [x] 3.4 Preserve `switch_config_allowed_operations` validation before invoking collection resource modules.
- [x] 3.5 Preserve destructive-command blocking for rendered commands, module command outputs, and any documented fallback raw configuration path.
- [x] 3.6 Preserve change reports containing current state, desired intent, command/module summaries, apply status, and verification outcome.
- [x] 3.7 Keep `c1emon.xikeos.xikeos_config` limited to documented fallback gaps rather than the primary declarative interface.

## 4. Verification and Documentation

- [x] 4.1 Update switch playbook and role documentation to describe the native XikeOS collection path and migration from the Cisco IOS adapter.
- [x] 4.2 Add or update tests/smoke checks for dependency metadata, inventory network OS selection, read-only command behavior, and VLAN/interface planning behavior.
- [x] 4.3 Run relevant local validation for OpenSpec artifacts and Ansible YAML syntax.
- [x] 4.4 If live switch access is available, run read-only smoke validation before any apply-enabled configuration workflow.
- [x] 4.5 Record any remaining collection capability gaps in documentation or follow-up tasks before archiving the change.

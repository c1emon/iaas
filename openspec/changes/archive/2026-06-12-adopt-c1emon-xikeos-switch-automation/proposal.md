## Why

The current switch automation uses `cisco.ios.ios` as a compatibility terminal adapter for SKS8300/Xike switches, which keeps the workflow dependent on a Cisco platform abstraction that does not match the managed devices. The `c1emon.xikeos` collection now provides a native XikeOS `cliconf`/terminal path and resource modules, making it possible to replace the adapter workaround while preserving the safety model already built in this repository.

## What Changes

- Add `c1emon.xikeos` as the project switch automation collection dependency and document installation through the repository collection requirements workflow.
- Replace the switch inventory network OS setting from `cisco.ios.ios` to the native `c1emon.xikeos.xikeos` platform while continuing to use `ansible.netcommon.network_cli` over SSH.
- Move read-only switch command execution toward `c1emon.xikeos.xikeos_command` and gathered resource modules where they provide equivalent safe behavior.
- Move declarative VLAN and interface configuration execution toward `c1emon.xikeos` resource modules while retaining repository-level apply gates, allowed-operation policy, reports, and post-state verification expectations.
- Avoid making `c1emon.xikeos.xikeos_config` the primary declarative configuration interface; reserve raw configuration lines for documented fallback cases only.

## Capabilities

### New Capabilities
- `xikeos-collection-switch-automation`: Native XikeOS collection dependency, inventory platform selection, and safe use of `c1emon.xikeos` command/resource modules for repository switch automation.

### Modified Capabilities
- `switch-cli-readonly-facts`: Replace the Cisco IOS terminal adapter requirement with the native XikeOS collection platform while preserving read-only SSH collection behavior.
- `sks8300-profile-readonly-facts`: Allow the read-only profile workflow to use collection-backed commands or gathered resource modules instead of only local command catalog execution where behavior is equivalent.
- `sks8300-config-resource-framework`: Allow declarative switch configuration to delegate VLAN/interface mutation to `c1emon.xikeos` resource modules while preserving apply gates, allowed operations, reporting, and verification.

## Impact

- Affected dependency files: `ansible/requirements.yml`, related setup documentation.
- Affected inventory/runtime configuration: `ansible/inventories/group_vars/switches.yml` and switch playbook documentation.
- Affected read-only workflow: `ansible/playbooks/switches/readonly-facts.yml`, `ansible/roles/switch_readonly_facts/`, and local SKS8300 command/profile helpers where replaced or adapted.
- Affected configuration workflow: `ansible/roles/switch_config/`, `ansible/module_utils/switch_profiles/sks8300/resources.py`, and switch vars/playbooks that declare VLAN/interface intent.
- External dependency: `c1emon.xikeos` collection, with runtime Python parser dependencies from that collection such as `ttp` and `textfsm` when collection facts/resource modules require them.

## Why

The SKS8300 read-only facts workflow is currently shaped around a small fixed CLI command list, which makes the role feel like a command runner instead of a reusable SKS8300-series adapter. Referencing MikroTik/RouterOS Ansible design patterns, the workflow should select data by platform profile and gather subsets while keeping command planning, parsing, and raw export policy inside a Python profile registry.

## What Changes

- **BREAKING**: Replace the user-facing `switch_cli_commands` command-list model for the read-only facts role with `switch_platform_profile` and `switch_readonly_gather_subset`.
- Introduce an SKS8300-series platform profile rather than a host-specific profile for `sw-core`.
- Add a MikroTik-inspired gather-subset model for read-only facts, with subsets such as `default`, `device`, `vlans`, and `interfaces`.
- Add a thin Ansible filter facade for profile operations and move SKS8300 command planning, parsing, and redaction core logic into `ansible/module_utils/switch_profiles/`.
- Add a role planning phase that asks the profile for the command plan before collection.
- Preserve SSH `network_cli` transport, `cisco.ios.ios` terminal adapter behavior, structured facts schema, export paths, and secret redaction behavior.
- Keep configuration changes out of scope while leaving a directory and API shape that can later support declarative config resource planning.

## Capabilities

### New Capabilities
- `sks8300-profile-readonly-facts`: Profile-driven SKS8300-series read-only facts collection using gather subsets, command planning, parser dispatch, and command raw-export policy.

### Modified Capabilities
- `switch-cli-readonly-facts`: Change the read-only facts workflow requirement from user-supplied fixed CLI command lists to SKS8300 profile-driven gather subset selection while preserving safe SSH collection and export behavior.

## Impact

- Affected Ansible role:
  - `ansible/roles/switch_readonly_facts/`
- Affected playbook entrypoint:
  - `ansible/playbooks/switches/readonly-facts.yml`
- Affected Python parsing/filter code:
  - `ansible/filter_plugins/switch_cli_facts.py`
  - new `ansible/filter_plugins/switch_profiles.py`
  - new `ansible/module_utils/switch_profiles/`
- Affected inventory/default variables:
  - replace read-only command variables with profile and gather subset defaults
  - keep SSH/network connection variables in inventory/group vars
- Affected documentation:
  - `ansible/playbooks/switches/README.md`
  - `ansible/roles/switch_readonly_facts/README.md`
- No switch configuration mutation is introduced by this change.

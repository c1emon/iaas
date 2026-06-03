## Why

The core switch (`SW_CORE`) is a non-officially supported SKS8300-12X device that can only be managed over Telnet, but the repository currently has no Ansible workflow for switch discovery or VLAN visibility. We need a safe read-only automation path that captures structured switch facts and VLAN state without relying on incompatible Cisco IOS modules.

## What Changes

- Add a read-only Ansible workflow for connecting to the SKS8300-12X switch over Telnet.
- Collect version/model information using the switch's CLI.
- Collect VLAN-related CLI outputs and parse them into structured facts.
- Support optional YAML and JSON exports of the parsed facts.
- Write generated exports under an `exports/` subdirectory, scoped by switch/host.
- Use only the verified pagination command `terminal length 0`.
- Redact secrets from any saved raw running configuration output.
- Avoid all mutating commands, including config mode, save, reload, delete, clear, format, and copy operations.

## Capabilities

### New Capabilities
- `switch-cli-readonly-facts`: Read-only Telnet collection, parsing, and export of SKS8300-12X switch version and VLAN facts.

### Modified Capabilities

None.

## Impact

- Affected code: Ansible inventory/group variables, new switch-oriented playbooks, and documentation under `ansible/`.
- Affected outputs: new generated switch exports under `exports/`.
- Dependencies: explicit use of `ansible.netcommon.telnet`; Ansible collection requirements may need to include `ansible.netcommon` for reproducible installs.
- Systems: `SW_CORE` / SKS8300-12X switch at the management address, accessed over Telnet only.
- Security: Telnet credentials must remain runtime-injected or otherwise secret-managed; raw running configuration output must be redacted before saving.

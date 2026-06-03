## Why

The switch read-only facts workflow currently collects credentials and command output over Telnet, which exposes authentication and configuration data in plaintext on the management network. The SKS8300-12X switch has been verified to support SSH with Ansible `network_cli`, so the facts collection path can be made encrypted without changing the read-only fact model.

## What Changes

- Replace Telnet-based switch facts collection with SSH `network_cli` and `ansible.netcommon.cli_command`.
- Use `cisco.ios.ios` as the `network_cli` terminal adapter for this SKS8300-12X workflow, while avoiding Cisco IOS configuration/resource modules.
- Rename Telnet-specific runtime variables and artifacts to SSH/CLI-neutral names where they describe the transport or collected outputs.
- Preserve the approved read-only command allowlist: `terminal length 0`, `show version`, `show vlan`, `show vlan brief`, and `show running-config`.
- Keep the workflow read-only; VLAN write/configuration management is explicitly out of scope for this change.
- Add or document the Python SSH dependency required by the selected Ansible connection backend.
- **BREAKING**: Runtime credentials move away from `SWITCH_TELNET_USER` / `SWITCH_TELNET_PASSWORD` toward SSH credential variables.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `switch-cli-readonly-facts`: Change collection transport requirements from Telnet to encrypted SSH `network_cli` while preserving read-only command and export behavior.

## Impact

- Affected playbooks and inventory variables:
  - `ansible/playbooks/switches/readonly-facts.yml`
  - `ansible/inventories/group_vars/switches.yml`
- Affected parsing/filter naming if Telnet-specific helper names are generalized.
- Affected documentation/readme text that currently describes Telnet output.
- Affected dependency/runtime setup for Ansible SSH transport, such as `paramiko` or `ansible-pylibssh`.
- No intended change to generated fact schemas, export formats, redaction behavior, or VLAN parsing semantics.

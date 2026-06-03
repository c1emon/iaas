## Context

The current switch facts playbook collects SKS8300-12X CLI output with `ansible.netcommon.telnet` while the inventory provides `switch_telnet_*` variables. That workflow is intentionally read-only, but Telnet transmits credentials and `show running-config` output in plaintext.

Manual and Ansible smoke testing showed the switch supports SSH and works with `ansible.netcommon.network_cli` when `ansible_network_os` is set to `cisco.ios.ios`. Read-only commands (`terminal length 0`, `show version`, `show vlan`, `show vlan brief`, `show running-config`) all succeed. VLAN write tests also succeeded through `cli_command`, but `ansible.netcommon.cli_config` failed because this switch enters configuration mode with `config` rather than Cisco IOS `configure terminal`.

## Goals / Non-Goals

**Goals:**

- Move read-only switch facts collection from Telnet to encrypted SSH.
- Preserve the existing read-only command allowlist and mutation guardrails.
- Preserve structured fact output, YAML/JSON export behavior, raw-output redaction, and export locations.
- Use a connection approach already verified against `sw-core`.
- Make transport naming clear enough that future maintenance does not confuse SSH collection with Telnet collection.

**Non-Goals:**

- Implement VLAN management or any other switch configuration workflow.
- Use `ansible.netcommon.cli_config`, Cisco IOS resource modules, or `ios_config` for this switch.
- Add Telnet fallback.
- Change the parsed switch fact schema except where field values naturally differ because the command transport changed.

## Decisions

### Use `network_cli` over SSH for collection

The facts playbook should use `ansible.netcommon.network_cli` and `ansible.netcommon.cli_command` instead of the Telnet module. This keeps the same CLI command model while encrypting credentials and command output in transit.

Alternative considered: keep Telnet as a fallback. This was rejected because it preserves the plaintext path, complicates variables, and weakens the safety goal of the migration.

### Use `cisco.ios.ios` only as the terminal adapter

The switch is not treated as Cisco IOS for configuration semantics. `cisco.ios.ios` is used because its `network_cli` terminal handling successfully logs in and runs commands against the SKS8300-12X prompt.

Alternative considered: `ansible.netcommon.default` / `default`. Both failed with `network os ... is not supported` in the current Ansible environment.

### Use `cli_command`, not `cli_config`

Read-only collection should use `ansible.netcommon.cli_command` for each approved command. The smoke tests showed `cli_config` sends `configure terminal`, which this switch rejects. Avoiding `cli_config` prevents accidental dependence on Cisco IOS configuration behavior.

Alternative considered: using Cisco IOS-specific modules. This was rejected because the device CLI is only partially Cisco-like and those modules may assume unsupported command syntax.

### Generalize Telnet-specific names where practical

Variables and local facts that describe the transport should move from `switch_telnet_*` to SSH/CLI names, such as `switch_ssh_*` for connection settings and `switch_cli_*` for command/output data. Parser helpers can be generalized from Telnet-specific names to CLI-specific names if they are touched by the migration.

Alternative considered: keep the old names for smaller diffs. This was rejected for user-facing variables and documentation because SSH collection with Telnet names would create long-term confusion.

## Risks / Trade-offs

- `cisco.ios.ios` is a compatibility adapter, not a device identity → Document this clearly and avoid Cisco IOS config/resource modules.
- SSH backend dependency may be missing → Add or document a Python SSH backend such as `paramiko` or `ansible-pylibssh` so `network_cli` can connect reliably.
- Loop result shape differs from Telnet module output → Normalize `cli_command` loop results into the same ordered command-output list expected by the existing parsers.
- Host key checking is enabled → Ensure the switch host key must be known before non-interactive runs, or document the required setup.
- Credential variable rename is breaking for operators → Call out the migration from Telnet environment variables to SSH environment variables.

## Migration Plan

1. Add or document the SSH backend dependency required for `network_cli`.
2. Update inventory/group variables from Telnet-specific settings to SSH/CLI settings.
3. Update `readonly-facts.yml` to connect with `network_cli` and run each approved command via `cli_command`.
4. Normalize `cli_command` loop results before passing them to the existing fact parser.
5. Update readme/raw-output summary wording from Telnet to SSH/CLI.
6. Validate read-only collection against `sw-core` and verify YAML/JSON exports still parse expected version and VLAN facts.

Rollback is to restore the previous Telnet playbook and Telnet credential variables. Because this is a read-only workflow, rollback does not require device configuration changes.

## Open Questions

- Should the project prefer `paramiko` for simplicity or `ansible-pylibssh` for the network CLI backend?
- Should the temporary smoke-test playbooks remain in the repository, be converted into documented manual validation tools, or be removed after implementation?

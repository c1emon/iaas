## 1. Dependency and Inventory Setup

- [x] 1.1 Choose and add/document the SSH backend for `network_cli` (`paramiko` or `ansible-pylibssh`).
- [x] 1.2 Replace Telnet switch group variables with SSH/CLI variables, including username, password, port, and network OS adapter settings.
- [x] 1.3 Update operator-facing credential expectations from `SWITCH_TELNET_USER` / `SWITCH_TELNET_PASSWORD` to SSH credential variables.

## 2. Read-Only Facts Playbook Migration

- [x] 2.1 Update `readonly-facts.yml` to use `ansible.netcommon.network_cli` with the verified `cisco.ios.ios` terminal adapter.
- [x] 2.2 Replace the `ansible.netcommon.telnet` collection task with `ansible.netcommon.cli_command` loop execution for the approved command list.
- [x] 2.3 Normalize `cli_command` loop results into the ordered raw-output list expected by the existing switch fact parser.
- [x] 2.4 Preserve the read-only command assertion and ensure mutating commands such as `config`, `configure`, `write`, `copy`, `reload`, `delete`, `clear`, and `format` remain blocked.
- [x] 2.5 Update task names, registered variable names, summaries, and generated README text to refer to SSH/CLI rather than Telnet.

## 3. Parser and Naming Cleanup

- [x] 3.1 Rename Telnet-specific filter/helper names to CLI-neutral names if required by the playbook migration.
- [x] 3.2 Update all references and tests for renamed filters/helpers without changing parsed fact schema semantics.
- [x] 3.3 Ensure raw running configuration redaction still applies before any raw config is written.

## 4. Validation

- [x] 4.1 Run the migrated read-only facts playbook against `sw-core` with SSH credentials and verify it completes without configuration-mode commands.
- [x] 4.2 Verify generated YAML and JSON exports still include expected version facts and VLAN/interface membership facts.
- [x] 4.3 Verify raw-output export, when enabled, writes SSH/CLI-neutral summary naming and redacts sensitive running-config lines.
- [x] 4.4 Run relevant Ansible lint or syntax checks for the changed playbooks and inventory variables.

## 5. Cleanup and Documentation

- [x] 5.1 Decide whether temporary network CLI smoke-test playbooks should be kept as validation utilities or removed.
- [x] 5.2 Document that `cisco.ios.ios` is used only as a terminal adapter for this switch and that Cisco IOS config/resource modules are not supported by this workflow.
- [x] 5.3 Document that VLAN write/configuration management is out of scope for this change despite being experimentally verified with `cli_command`.

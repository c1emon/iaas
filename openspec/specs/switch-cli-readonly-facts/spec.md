# switch-cli-readonly-facts Specification

## Purpose

Provide a safe read-only SSH network CLI workflow for collecting and parsing SKS8300-12X switch version and VLAN facts without mutating switch configuration, with file export handled by caller-owned workflows.
## Requirements
### Requirement: SSH network CLI read-only switch collection
The system SHALL collect XikeOS switch data over encrypted SSH using Ansible `network_cli` and the native `c1emon.xikeos` facts interface without mutating switch configuration.

#### Scenario: Collect switch data without mutation over SSH
- **WHEN** the switch facts playbook runs against a configured switch host
- **THEN** the playbook SHALL connect over SSH using `ansible.netcommon.network_cli`
- **AND** the playbook SHALL use the native XikeOS collection platform for switch terminal and cliconf behavior
- **AND** the playbook SHALL collect structured state through `c1emon.xikeos.xikeos_facts`
- **AND** the playbook SHALL NOT enter configuration mode or run mutating commands such as `config`, `configure`, `write`, `copy`, `reload`, `delete`, `clear`, or `format`

#### Scenario: Use native XikeOS terminal adapter without Cisco configuration modules
- **WHEN** the switch facts playbook connects to a XikeOS switch through `network_cli`
- **THEN** it SHALL use `ansible_network_os: c1emon.xikeos.xikeos` for CLI transport compatibility
- **AND** it SHALL NOT require the Cisco IOS terminal adapter for collecting read-only facts
- **AND** it SHALL NOT use Cisco IOS configuration or resource modules for collecting read-only facts

### Requirement: Role-based read-only facts workflow packaging
The system SHALL expose the XikeOS read-only facts workflow through the switch read-only playbook using collection-native facts without requiring a separate role when the role would only wrap `c1emon.xikeos.xikeos_facts`.

#### Scenario: Run read-only facts through playbook entrypoint
- **WHEN** the operator runs `ansible/playbooks/switches/readonly-facts.yml`
- **THEN** the playbook SHALL collect facts with `c1emon.xikeos.xikeos_facts`
- **AND** the workflow SHALL expose collection-native `ansible_net_*` and `ansible_network_resources` data to caller-owned export tasks
- **AND** file export, if desired, SHALL be performed by playbook-level or caller-owned tasks after facts collection completes

#### Scenario: Avoid redundant read-only role wrapper
- **WHEN** read-only facts collection requires no reusable repository policy beyond runtime validation and collection module invocation
- **THEN** the workflow SHALL NOT require a dedicated `switch_readonly_facts` role
- **AND** direct playbook tasks SHALL make the native collection call and exported variables clear to operators

#### Scenario: Keep host connection settings outside playbook implementation
- **WHEN** the read-only facts workflow is used for a switch host
- **THEN** host connection settings such as `ansible_connection`, `ansible_network_os`, `ansible_user`, `ansible_password`, and `ansible_port` SHALL remain supplied by inventory or runtime variables rather than being hard-coded in tasks

### Requirement: SSH credential configuration
The system SHALL obtain switch SSH credentials from runtime-provided SSH credential variables rather than Telnet credential variables.

#### Scenario: Validate SSH credentials before collection
- **WHEN** the switch facts playbook starts
- **THEN** it SHALL require non-empty SSH username and password values
- **AND** the validation failure message SHALL instruct the operator to provide SSH credential variables

#### Scenario: Avoid Telnet credentials for SSH collection
- **WHEN** the switch facts playbook collects read-only facts over SSH
- **THEN** it SHALL NOT require `SWITCH_TELNET_USER` or `SWITCH_TELNET_PASSWORD`

### Requirement: Fixed pagination command
The system SHALL rely on the native XikeOS collection facts path for pagination handling and SHALL only use explicit pagination commands in separate smoke or fallback command workflows.

#### Scenario: Pagination setup
- **WHEN** the switch facts workflow uses `c1emon.xikeos.xikeos_facts`
- **THEN** it SHALL NOT require repository-level command planning for `terminal length 0`
- **AND** any explicit pagination command SHALL be limited to smoke, debug, or documented fallback command workflows

### Requirement: YAML and JSON exports
The system SHALL support configurable YAML and JSON export of parsed switch facts through the playbook-level export workflow rather than through facts collection itself.

#### Scenario: Export selected formats
- **WHEN** the playbook-level export workflow is enabled and the user configures YAML, JSON, or both output formats
- **THEN** the export workflow SHALL write the selected structured export files from `switch_facts`
- **AND** facts collection SHALL remain usable without writing those files

### Requirement: Export location
The system SHALL allow the playbook-level export workflow to write generated switch exports under the repository `exports/` directory in a switch-specific subdirectory.

#### Scenario: Write exports under repository exports tree
- **WHEN** switch facts are exported for inventory host `sw-core`
- **THEN** generated outputs SHALL be written under `exports/switches/sw-core/` or a timestamped child directory beneath it by the export workflow
- **AND** facts collection SHALL not create export directories

### Requirement: Secret redaction for raw running configuration
The system SHALL ensure any saved raw running configuration output is redacted before being written by the playbook-level export workflow.

#### Scenario: Redact plaintext user password
- **WHEN** raw `show running-config` output contains a line such as `username admin privilege 15 password 0 admin`
- **THEN** any saved raw running configuration export SHALL replace the secret value with a redacted placeholder
- **AND** raw running configuration export SHALL only be produced by a separately documented smoke, debug, or fallback workflow

#### Scenario: Redact network management secrets
- **WHEN** raw configuration output contains password, RADIUS secret, TACACS secret, or SNMP community lines
- **THEN** any saved raw running configuration export SHALL redact the secret values before writing the file
- **AND** facts collection SHALL not write raw configuration files directly

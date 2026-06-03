# switch-cli-readonly-facts Specification

## Purpose

Provide a safe read-only SSH network CLI workflow for collecting and parsing SKS8300-12X switch version and VLAN facts without mutating switch configuration, with file export handled by caller-owned workflows.
## Requirements
### Requirement: SSH network CLI read-only switch collection
The system SHALL collect SKS8300-series switch data over encrypted SSH using Ansible `network_cli` and only approved read-only commands derived from the configured platform profile and gather subsets.

#### Scenario: Collect switch data without mutation over SSH
- **WHEN** the switch facts playbook runs against a configured switch host
- **THEN** the playbook SHALL connect over SSH using `ansible.netcommon.network_cli`
- **AND** the playbook SHALL build CLI collection from the configured `switch_platform_profile` and `switch_readonly_gather_subset`
- **AND** the playbook SHALL send `terminal length 0` before data collection commands when required by the profile
- **AND** the playbook SHALL NOT enter configuration mode or run mutating commands such as `config`, `configure`, `write`, `copy`, `reload`, `delete`, `clear`, or `format`

#### Scenario: Use verified terminal adapter without Cisco configuration modules
- **WHEN** the switch facts playbook connects to the SKS8300-12X switch through `network_cli`
- **THEN** it SHALL use the verified `cisco.ios.ios` terminal adapter for CLI transport compatibility
- **AND** it SHALL NOT use Cisco IOS configuration or resource modules for collecting read-only facts

### Requirement: Role-based read-only facts workflow packaging
The system SHALL expose the SKS8300 read-only facts workflow through a reusable Ansible role that collects and parses facts without intrinsic file persistence side effects, while preserving the existing playbook entrypoint behavior through caller-owned export tasks.

#### Scenario: Run read-only facts through role entrypoint
- **WHEN** the operator runs `ansible/playbooks/switches/readonly-facts.yml`
- **THEN** the playbook SHALL invoke a dedicated switch read-only facts role
- **AND** the role SHALL collect the approved SSH `network_cli` command outputs
- **AND** the role SHALL parse structured switch facts into role output variables
- **AND** file export, if desired, SHALL be performed by playbook-level or caller-owned tasks after the role completes

#### Scenario: Keep host connection settings outside role defaults
- **WHEN** the role is used for a switch host
- **THEN** host connection settings such as `ansible_connection`, `ansible_network_os`, `ansible_user`, `ansible_password`, and `ansible_port` SHALL remain supplied by inventory or runtime variables rather than being hard-coded in role tasks

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
The system SHALL disable switch CLI pagination only by using `terminal length 0` when pagination setup is required by the configured platform profile.

#### Scenario: Pagination setup
- **WHEN** the switch facts workflow plans command collection for an SKS8300 profile that requires pagination setup
- **THEN** it SHALL send `terminal length 0` before data collection commands
- **AND** it SHALL NOT attempt alternative pagination commands such as `screen-rows per-page 0`

### Requirement: Version fact parsing
The system SHALL parse `show version` output into structured device facts.

#### Scenario: Parse SKS8300 version output
- **WHEN** `show version` output contains model, software version, BootRom version, serial number, MAC addresses, and uptime
- **THEN** the structured facts SHALL include the device model, software version, BootRom version, serial number, CPU MAC, VLAN MAC, and uptime

### Requirement: VLAN fact parsing
The system SHALL parse VLAN definitions and interface VLAN membership into structured facts.

#### Scenario: Parse VLAN definitions
- **WHEN** collected output contains VLAN definitions such as `vlan 10` and `name dev`
- **THEN** the structured facts SHALL include VLAN ID `10` with name `dev`

#### Scenario: Parse interface VLAN membership
- **WHEN** collected running configuration contains hybrid, trunk, or access switchport lines
- **THEN** the structured facts SHALL include each interface's mode and VLAN membership using structured lists of VLAN IDs

### Requirement: YAML and JSON exports
The system SHALL support configurable YAML and JSON export of parsed switch facts through the playbook-level export workflow rather than through the facts role itself.

#### Scenario: Export selected formats
- **WHEN** the playbook-level export workflow is enabled and the user configures YAML, JSON, or both output formats
- **THEN** the export workflow SHALL write the selected structured export files from `switch_facts`
- **AND** the `switch_readonly_facts` role SHALL remain usable without writing those files

### Requirement: Export location
The system SHALL allow the playbook-level export workflow to write generated switch exports under the repository `exports/` directory in a switch-specific subdirectory.

#### Scenario: Write exports under repository exports tree
- **WHEN** switch facts are exported for inventory host `sw-core`
- **THEN** generated outputs SHALL be written under `exports/switches/sw-core/` or a timestamped child directory beneath it by the export workflow
- **AND** the facts role SHALL not create export directories as part of facts collection

### Requirement: Secret redaction for raw running configuration
The system SHALL ensure any saved raw running configuration output is redacted before being written by the playbook-level export workflow.

#### Scenario: Redact plaintext user password
- **WHEN** raw `show running-config` output contains a line such as `username admin privilege 15 password 0 admin`
- **THEN** any saved raw running configuration export SHALL replace the secret value with a redacted placeholder
- **AND** the redacted content SHALL come from the profile-generated raw export plan consumed by the export workflow

#### Scenario: Redact network management secrets
- **WHEN** raw configuration output contains password, RADIUS secret, TACACS secret, or SNMP community lines
- **THEN** any saved raw running configuration export SHALL redact the secret values before writing the file
- **AND** the facts role SHALL not write raw configuration files directly

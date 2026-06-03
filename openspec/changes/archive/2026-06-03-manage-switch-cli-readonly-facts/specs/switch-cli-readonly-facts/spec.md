## ADDED Requirements

### Requirement: Telnet read-only switch collection
The system SHALL collect SKS8300-12X switch data over Telnet using only read-only commands.

#### Scenario: Collect switch data without mutation
- **WHEN** the switch facts playbook runs against a configured switch host
- **THEN** the playbook SHALL connect over Telnet and run `terminal length 0`, `show version`, `show vlan`, `show vlan brief`, and `show running-config`
- **AND** the playbook SHALL NOT enter configuration mode or run mutating commands such as `config`, `write`, `copy`, `reload`, `delete`, `clear`, or `format`

### Requirement: Fixed pagination command
The system SHALL disable switch CLI pagination only by using `terminal length 0`.

#### Scenario: Pagination setup
- **WHEN** the switch facts playbook starts command collection
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
The system SHALL support configurable YAML and JSON export of parsed switch facts.

#### Scenario: Export selected formats
- **WHEN** the user configures YAML, JSON, or both output formats
- **THEN** the playbook SHALL write the selected structured export files

### Requirement: Export location
The system SHALL write generated switch exports under the repository `exports/` directory in a switch-specific subdirectory.

#### Scenario: Write exports under repository exports tree
- **WHEN** switch facts are exported for inventory host `sw-core`
- **THEN** generated outputs SHALL be written under `exports/switches/sw-core/` or a timestamped child directory beneath it

### Requirement: Secret redaction for raw running configuration
The system SHALL redact secrets before saving raw running configuration output.

#### Scenario: Redact plaintext user password
- **WHEN** raw `show running-config` output contains a line such as `username admin privilege 15 password 0 admin`
- **THEN** any saved raw running configuration export SHALL replace the secret value with a redacted placeholder

#### Scenario: Redact network management secrets
- **WHEN** raw configuration output contains password, RADIUS secret, TACACS secret, or SNMP community lines
- **THEN** any saved raw running configuration export SHALL redact the secret values before writing the file

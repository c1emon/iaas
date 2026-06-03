## ADDED Requirements

### Requirement: SSH network CLI read-only switch collection
The system SHALL collect SKS8300-12X switch data over encrypted SSH using Ansible `network_cli` and only approved read-only commands.

#### Scenario: Collect switch data without mutation over SSH
- **WHEN** the switch facts playbook runs against a configured switch host
- **THEN** the playbook SHALL connect over SSH using `ansible.netcommon.network_cli`
- **AND** the playbook SHALL run `terminal length 0`, `show version`, `show vlan`, `show vlan brief`, and `show running-config`
- **AND** the playbook SHALL NOT enter configuration mode or run mutating commands such as `config`, `configure`, `write`, `copy`, `reload`, `delete`, `clear`, or `format`

#### Scenario: Use verified terminal adapter without Cisco configuration modules
- **WHEN** the switch facts playbook connects to the SKS8300-12X switch through `network_cli`
- **THEN** it SHALL use the verified `cisco.ios.ios` terminal adapter for CLI transport compatibility
- **AND** it SHALL NOT use Cisco IOS configuration or resource modules for collecting read-only facts

### Requirement: SSH credential configuration
The system SHALL obtain switch SSH credentials from runtime-provided SSH credential variables rather than Telnet credential variables.

#### Scenario: Validate SSH credentials before collection
- **WHEN** the switch facts playbook starts
- **THEN** it SHALL require non-empty SSH username and password values
- **AND** the validation failure message SHALL instruct the operator to provide SSH credential variables

#### Scenario: Avoid Telnet credentials for SSH collection
- **WHEN** the switch facts playbook collects read-only facts over SSH
- **THEN** it SHALL NOT require `SWITCH_TELNET_USER` or `SWITCH_TELNET_PASSWORD`

## REMOVED Requirements

### Requirement: Telnet read-only switch collection
**Reason**: Telnet transmits switch credentials and collected CLI output, including running configuration content, in plaintext. The switch supports SSH collection through Ansible `network_cli`, so the read-only facts workflow no longer needs Telnet transport.

**Migration**: Configure switch SSH credentials and run the switch facts playbook over `ansible.netcommon.network_cli`. The approved command list and structured exports remain unchanged.

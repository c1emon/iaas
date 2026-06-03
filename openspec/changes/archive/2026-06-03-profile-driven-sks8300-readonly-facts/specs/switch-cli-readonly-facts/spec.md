## MODIFIED Requirements

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

### Requirement: Fixed pagination command
The system SHALL disable switch CLI pagination only by using `terminal length 0` when pagination setup is required by the configured platform profile.

#### Scenario: Pagination setup
- **WHEN** the switch facts workflow plans command collection for an SKS8300 profile that requires pagination setup
- **THEN** it SHALL send `terminal length 0` before data collection commands
- **AND** it SHALL NOT attempt alternative pagination commands such as `screen-rows per-page 0`

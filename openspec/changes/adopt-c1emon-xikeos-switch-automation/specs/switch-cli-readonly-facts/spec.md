## MODIFIED Requirements

### Requirement: SSH network CLI read-only switch collection
The system SHALL collect SKS8300/XikeOS-series switch data over encrypted SSH using Ansible `network_cli` and only approved read-only command or gathered-resource operations derived from the configured switch workflow.

#### Scenario: Collect switch data without mutation over SSH
- **WHEN** the switch facts playbook runs against a configured switch host
- **THEN** the playbook SHALL connect over SSH using `ansible.netcommon.network_cli`
- **AND** the playbook SHALL use the native XikeOS collection platform for switch terminal and cliconf behavior
- **AND** the playbook SHALL build read-only collection from configured gather subsets, collection command modules, gathered resource modules, or compatibility profile planning
- **AND** the playbook SHALL NOT enter configuration mode or run mutating commands such as `config`, `configure`, `write`, `copy`, `reload`, `delete`, `clear`, or `format`

#### Scenario: Use native XikeOS terminal adapter without Cisco configuration modules
- **WHEN** the switch facts playbook connects to the SKS8300/XikeOS switch through `network_cli`
- **THEN** it SHALL use `ansible_network_os: c1emon.xikeos.xikeos` for CLI transport compatibility
- **AND** it SHALL NOT require the Cisco IOS terminal adapter for collecting read-only facts
- **AND** it SHALL NOT use Cisco IOS configuration or resource modules for collecting read-only facts

### Requirement: Fixed pagination command
The system SHALL disable switch CLI pagination only through the native XikeOS collection path or by using `terminal length 0` when pagination setup is required by a compatibility profile.

#### Scenario: Pagination setup
- **WHEN** the switch facts workflow requires explicit pagination setup for SKS8300/XikeOS command collection
- **THEN** it SHALL send `terminal length 0` before data collection commands unless the native collection module handles pagination internally
- **AND** it SHALL NOT attempt alternative pagination commands such as `screen-rows per-page 0`

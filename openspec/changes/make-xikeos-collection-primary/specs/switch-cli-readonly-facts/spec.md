## MODIFIED Requirements

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
The system SHALL expose the XikeOS read-only facts workflow through a reusable Ansible role that collects collection-native facts without intrinsic file persistence side effects.

#### Scenario: Run read-only facts through role entrypoint
- **WHEN** the operator runs `ansible/playbooks/switches/readonly-facts.yml`
- **THEN** the playbook SHALL invoke a dedicated switch read-only facts role
- **AND** the role SHALL collect facts with `c1emon.xikeos.xikeos_facts`
- **AND** the role SHALL expose collection-native `ansible_net_*` and `ansible_network_resources` data to caller-owned tasks
- **AND** file export, if desired, SHALL be performed by playbook-level or caller-owned tasks after the role completes

#### Scenario: Keep host connection settings outside role defaults
- **WHEN** the role is used for a switch host
- **THEN** host connection settings such as `ansible_connection`, `ansible_network_os`, `ansible_user`, `ansible_password`, and `ansible_port` SHALL remain supplied by inventory or runtime variables rather than being hard-coded in role tasks

### Requirement: Fixed pagination command
The system SHALL rely on the native XikeOS collection facts path for pagination handling and SHALL only use explicit pagination commands in separate smoke or fallback command workflows.

#### Scenario: Pagination setup
- **WHEN** the switch facts workflow uses `c1emon.xikeos.xikeos_facts`
- **THEN** it SHALL NOT require repository-level command planning for `terminal length 0`
- **AND** any explicit pagination command SHALL be limited to smoke, debug, or documented fallback command workflows

## REMOVED Requirements

### Requirement: Version fact parsing
**Reason**: `c1emon.xikeos.xikeos_facts` is now the primary facts source, and the repository no longer owns `show version` parsing into the old `switch_facts.device` schema.
**Migration**: Use collection-provided `ansible_net_*` facts such as `ansible_net_model`, `ansible_net_version`, and `ansible_net_serialnum`.

### Requirement: VLAN fact parsing
**Reason**: `ansible_network_resources` is now the canonical resource state schema, and the repository no longer parses VLAN facts into the old `switch_facts.vlans` and `switch_facts.interfaces` shapes.
**Migration**: Use `ansible_network_resources.vlans`, `ansible_network_resources.interfaces`, and `ansible_network_resources.l2_interfaces`.

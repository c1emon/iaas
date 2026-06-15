## ADDED Requirements

### Requirement: Native XikeOS collection dependency
The system SHALL declare `c1emon.xikeos` as the switch automation collection dependency through the repository Ansible collection requirements workflow.

#### Scenario: Install repository Ansible collections
- **WHEN** an operator installs Ansible collections for this repository from the requirements file
- **THEN** the `c1emon.xikeos` collection SHALL be included with the other required collections
- **AND** switch documentation SHALL direct operators to use the repository requirements installation workflow

#### Scenario: Document collection runtime parser dependencies
- **WHEN** collection-backed facts or resource modules require Python parser libraries on the control node
- **THEN** the repository documentation SHALL identify those runtime dependencies
- **AND** the documentation SHALL make clear that Ansible collection installation does not automatically install Python packages

### Requirement: Native XikeOS network OS selection
The system SHALL use the native XikeOS Ansible platform FQCN for switch hosts managed through the `c1emon.xikeos` collection.

#### Scenario: Configure switch host connection
- **WHEN** a switch host is configured for repository switch automation
- **THEN** the host or switch group SHALL use `ansible_network_os: c1emon.xikeos.xikeos`
- **AND** it SHALL continue to use `ansible_connection: ansible.netcommon.network_cli` for SSH network CLI transport

#### Scenario: Avoid Cisco platform adapter for XikeOS workflows
- **WHEN** a switch workflow uses `c1emon.xikeos` modules or plugins
- **THEN** it SHALL NOT require `ansible_network_os: cisco.ios.ios` for terminal compatibility

### Requirement: Prefer lifecycle-safe collection modules
The system SHALL prefer `c1emon.xikeos` command and resource modules over generic raw CLI execution when those modules provide equivalent safe behavior.

#### Scenario: Run read-only operational commands
- **WHEN** the repository needs to run a non-mutating XikeOS operational command through the native collection path
- **THEN** it SHALL use `c1emon.xikeos.xikeos_command` or an equivalent gathered resource module rather than a Cisco-platform command path
- **AND** the task SHALL report no configuration change for read-only command collection

#### Scenario: Manage declarative VLAN and interface resources
- **WHEN** the repository applies supported VLAN or interface intent to a XikeOS switch
- **THEN** it SHALL prefer lifecycle-safe `c1emon.xikeos` resource modules such as VLAN, interface, L2 interface, L3 interface, or LAG modules
- **AND** it SHALL preserve check-mode planning before sending mutating configuration

### Requirement: Raw configuration fallback constraints
The system SHALL treat raw XikeOS configuration lines as a fallback path rather than the primary declarative switch configuration interface.

#### Scenario: Reject raw config as default resource model
- **WHEN** an operator attempts to use raw arbitrary configuration lines as the normal repository switch configuration interface
- **THEN** the workflow SHALL reject or avoid that path
- **AND** it SHALL instruct the operator to use supported declarative resource intent or documented collection resource modules

#### Scenario: Use raw config only for documented gaps
- **WHEN** no lifecycle-safe `c1emon.xikeos` resource module exists for a required switch feature
- **THEN** any fallback raw configuration use SHALL be explicitly documented
- **AND** repository guardrails SHALL still validate allowed operations and block destructive commands before apply

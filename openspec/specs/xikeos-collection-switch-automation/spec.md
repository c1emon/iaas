# xikeos-collection-switch-automation Specification

## Purpose
TBD - created by archiving change adopt-c1emon-xikeos-switch-automation. Update Purpose after archive.
## Requirements
### Requirement: Native XikeOS collection dependency
The system SHALL declare `c1emon.xikeos` v0.2.x as the switch automation collection dependency through the repository Ansible collection requirements workflow.

#### Scenario: Install repository Ansible collections
- **WHEN** an operator installs Ansible collections for this repository from the requirements file
- **THEN** the `c1emon.xikeos` collection SHALL be included with the other required collections
- **AND** the installed version SHALL satisfy the repository's v0.2.x switch automation baseline
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
The system SHALL prefer `c1emon.xikeos` facts and resource modules over generic raw CLI execution or repository-local resource adapters when those modules provide equivalent or stronger behavior.

#### Scenario: Collect read-only switch state
- **WHEN** the repository needs structured read-only XikeOS switch state through the native collection path
- **THEN** it SHALL use `c1emon.xikeos.xikeos_facts` as the normal facts collection interface
- **AND** it SHALL treat `ansible_net_*` and `ansible_network_resources` as the resulting authoritative state schema
- **AND** the task SHALL report no configuration change for read-only collection

#### Scenario: Run ad hoc read-only operational commands
- **WHEN** the repository needs to run a non-mutating XikeOS operational command for smoke testing or debugging
- **THEN** it MAY use `c1emon.xikeos.xikeos_command` rather than a Cisco-platform command path
- **AND** the task SHALL report no configuration change for read-only command collection

#### Scenario: Manage declarative switch resources
- **WHEN** the repository previews or applies supported switch resources to a XikeOS switch
- **THEN** it SHALL invoke lifecycle-safe `c1emon.xikeos` resource modules such as VLAN, interface, L2 interface, L3 interface, LAG, static route, or ACL modules directly
- **AND** it SHALL pass collection-native `state` and `config` inputs to those modules
- **AND** it SHALL preserve check-mode, rendered, gathered, or equivalent module planning before sending mutating configuration

#### Scenario: Avoid repository-local resource adapters
- **WHEN** a lifecycle-safe `c1emon.xikeos` resource module exists for a switch feature
- **THEN** the repository SHALL NOT maintain a parallel Python resource adapter for that feature's schema, diff, command generation, or verification
- **AND** model-specific or firmware-specific adaptation SHALL remain inside the collection module or plugin implementation

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

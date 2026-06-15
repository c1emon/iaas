## MODIFIED Requirements

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

### Requirement: Prefer lifecycle-safe collection modules
The system SHALL prefer `c1emon.xikeos` facts and resource modules over generic raw CLI execution when those modules provide equivalent or stronger behavior.

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
- **WHEN** the repository applies supported switch resource intent to a XikeOS switch
- **THEN** it SHALL prefer lifecycle-safe `c1emon.xikeos` resource modules such as VLAN, interface, L2 interface, L3 interface, LAG, static route, or ACL modules
- **AND** it SHALL preserve check-mode, rendered, gathered, or equivalent module planning before sending mutating configuration

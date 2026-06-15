## MODIFIED Requirements

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

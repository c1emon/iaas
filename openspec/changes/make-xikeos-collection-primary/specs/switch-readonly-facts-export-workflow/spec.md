## MODIFIED Requirements

### Requirement: Playbook-level switch facts export workflow
The system SHALL provide a caller-owned export workflow for writing collection-native switch facts to repository files without making file persistence an intrinsic behavior of the facts role.

#### Scenario: Export switch facts after role collection
- **WHEN** `playbooks/switches/readonly-facts.yml` runs the read-only facts role and export is enabled by the playbook workflow
- **THEN** the playbook-level export workflow SHALL write configured structured exports from collection-native facts
- **AND** the exported data SHALL include `ansible_net_*` facts and `ansible_network_resources` when collected
- **AND** it SHALL write files under the configured switch export directory

#### Scenario: Avoid profile raw output exports in normal workflow
- **WHEN** raw output export behavior is requested from the normal read-only facts workflow
- **THEN** the export workflow SHALL NOT depend on SKS8300 profile command IDs or `switch_raw_export_items`
- **AND** any raw command output export SHALL require a separately documented smoke, debug, or fallback workflow

#### Scenario: Summarize collection outside the facts role
- **WHEN** facts export is enabled by the playbook workflow
- **THEN** the export workflow SHALL write a collection summary using role output variables such as collection module name, requested gather subsets, requested network resources, transport, and terminal adapter

### Requirement: Export variables are caller-owned
The system SHALL keep export path, format, and raw-save controls outside the `switch_readonly_facts` role defaults.

#### Scenario: Configure export at playbook scope
- **WHEN** the operator uses the switch read-only facts playbook
- **THEN** export variables such as formats, export directory, and raw output behavior SHALL be defined by the playbook or caller
- **AND** the facts role SHALL not require those variables to collect collection-native facts

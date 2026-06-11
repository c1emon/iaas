## MODIFIED Requirements

### Requirement: SKS8300 profile-driven gather subset selection
The system SHALL expose SKS8300/XikeOS-series read-only facts through a gather subset model that may use native `c1emon.xikeos` command or gathered-resource modules, while retaining compatibility profile behavior where collection output does not yet provide equivalent facts.

#### Scenario: Select default SKS8300 facts by subset
- **WHEN** the operator runs the read-only facts workflow without overriding read-only fact selection
- **THEN** the workflow SHALL collect the default configured `switch_readonly_gather_subset` values
- **AND** it SHALL use native `c1emon.xikeos` collection operations where they provide equivalent read-only data
- **AND** it SHALL not require the operator to provide CLI command strings

#### Scenario: Select specific SKS8300 fact subsets
- **WHEN** the operator configures `switch_readonly_gather_subset` with supported subsets such as `device`, `vlans`, and `interfaces`
- **THEN** the workflow SHALL collect only the read-only data needed by those subsets plus required setup operations
- **AND** it SHALL parse, adapt, or pass through structured facts for the selected subsets into the repository fact schema

#### Scenario: Reject unsupported profile or subset
- **WHEN** the operator configures an unsupported switch profile, collection-backed subset, or compatibility subset value
- **THEN** the workflow SHALL fail before command collection
- **AND** the failure SHALL identify the invalid profile or subset value

### Requirement: Thin Ansible facade and reusable fact adaptation
The system SHALL expose Ansible-facing read-only switch fact operations through a thin facade that can delegate to native collection modules or compatibility SKS8300 profile utilities.

#### Scenario: Build collection through facade
- **WHEN** the role needs read-only switch facts
- **THEN** it SHALL call Ansible-facing tasks or filters that select the native collection path or compatibility profile path
- **AND** the selected path SHALL be based on supported subsets and equivalent output availability rather than user-provided command strings

#### Scenario: Adapt collection facts to repository schema
- **WHEN** command output or gathered resource data has been collected
- **THEN** the workflow SHALL map native collection results or compatibility command results into stable repository `switch_facts` output
- **AND** it SHALL preserve existing export workflow expectations unless a spec explicitly changes the fact schema

#### Scenario: Keep redaction reusable for raw exports
- **WHEN** read-only facts include raw running configuration content eligible for export
- **THEN** redaction behavior SHALL remain reusable outside the read-only role entrypoint
- **AND** plaintext management secrets SHALL NOT be exposed as file-safe export items

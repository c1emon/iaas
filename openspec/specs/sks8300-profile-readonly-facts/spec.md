# sks8300-profile-readonly-facts Specification

## Purpose
TBD - created by archiving change profile-driven-sks8300-readonly-facts. Update Purpose after archive.
## Requirements
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

### Requirement: Profile command planning and read-only policy
The system SHALL derive switch CLI commands from the SKS8300 profile command catalog and enforce read-only command policy before collection.

#### Scenario: Build command plan from SKS8300 profile
- **WHEN** the workflow plans collection for selected gather subsets
- **THEN** it SHALL build an ordered command plan from the SKS8300 profile command catalog
- **AND** each planned command SHALL include a stable command ID, CLI command string, read-only flag, sensitivity flag, and raw export policy

#### Scenario: Prevent mutating planned commands
- **WHEN** the command plan is built
- **THEN** every planned command SHALL be marked read-only
- **AND** the workflow SHALL reject any planned command that matches known mutating prefixes such as `config`, `configure`, `write`, `copy`, `reload`, `delete`, `clear`, or `format`

#### Scenario: Preserve pagination setup ordering
- **WHEN** the command plan includes switch CLI pagination setup
- **THEN** `terminal length 0` SHALL be planned before data collection commands
- **AND** the pagination setup command SHALL not be exported as a structured fact source

### Requirement: Thin Ansible filter facade and reusable profile core
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

### Requirement: Command-level raw export policy
The system SHALL decide raw output export eligibility and redaction using command-level policy from the SKS8300 profile, and SHALL expose that policy as export-plan data for caller-owned export workflows.

#### Scenario: Export non-sensitive raw command output
- **WHEN** raw output export is enabled by a caller-owned export workflow and a planned command is non-sensitive with raw export allowed
- **THEN** the profile-generated export plan SHALL include that command output with the command ID or documented filename mapping
- **AND** the caller-owned export workflow MAY write that planned item to the raw output directory

#### Scenario: Redact sensitive running configuration output
- **WHEN** raw output export is enabled by a caller-owned export workflow and the planned command is `show_running_config`
- **THEN** the profile-generated export plan SHALL provide only redacted running configuration output for that item
- **AND** it SHALL NOT expose plaintext management secrets as a file-safe export item

#### Scenario: Summarize command plan and collection
- **WHEN** raw output export is enabled by a caller-owned export workflow
- **THEN** the export workflow SHALL be able to summarize transport, terminal adapter, planned command IDs, collected result count, and normalized output lengths from role output variables

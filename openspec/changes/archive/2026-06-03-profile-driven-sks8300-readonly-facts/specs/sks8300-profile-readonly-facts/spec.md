## ADDED Requirements

### Requirement: SKS8300 profile-driven gather subset selection
The system SHALL expose SKS8300-series read-only facts through a platform profile and gather subset model rather than through user-supplied CLI command lists.

#### Scenario: Select default SKS8300 facts by subset
- **WHEN** the operator runs the read-only facts workflow without overriding read-only fact selection
- **THEN** the workflow SHALL use `switch_platform_profile: sks8300`
- **AND** it SHALL collect the default configured `switch_readonly_gather_subset` values
- **AND** it SHALL not require the operator to provide CLI command strings

#### Scenario: Select specific SKS8300 fact subsets
- **WHEN** the operator configures `switch_readonly_gather_subset` with supported subsets such as `device`, `vlans`, and `interfaces`
- **THEN** the workflow SHALL collect only the commands needed by those subsets plus required setup commands
- **AND** it SHALL parse and export structured facts for the selected subsets

#### Scenario: Reject unsupported profile or subset
- **WHEN** the operator configures an unsupported `switch_platform_profile` or unsupported `switch_readonly_gather_subset` value
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
The system SHALL expose Ansible-facing profile operations through thin filter plugins backed by reusable Python module utilities.

#### Scenario: Build plan through filter facade
- **WHEN** the role needs a command plan
- **THEN** it SHALL call an Ansible filter facade function
- **AND** the facade SHALL delegate SKS8300 profile lookup and planning to `ansible/module_utils/switch_profiles/`

#### Scenario: Parse facts through profile core
- **WHEN** command output has been collected
- **THEN** the workflow SHALL map command results by stable command ID
- **AND** it SHALL ask the SKS8300 profile core to parse selected gather subsets into structured facts

#### Scenario: Keep profile logic reusable for future configuration roles
- **WHEN** the read-only facts role uses SKS8300-specific command, parser, and redaction behavior
- **THEN** those behaviors SHALL live outside the read-only role directory
- **AND** they SHALL be reusable by a future configuration workflow without sharing the read-only role entrypoint

### Requirement: Command-level raw export policy
The system SHALL decide raw output exports using command-level policy from the SKS8300 profile.

#### Scenario: Export non-sensitive raw command output
- **WHEN** raw output export is enabled and a planned command is non-sensitive with raw export allowed
- **THEN** the workflow SHALL write that command output to the raw output directory using the command ID or documented filename mapping

#### Scenario: Redact sensitive running configuration output
- **WHEN** raw output export is enabled and the planned command is `show_running_config`
- **THEN** the workflow SHALL write only redacted running configuration output
- **AND** it SHALL NOT write plaintext management secrets to disk

#### Scenario: Summarize command plan and collection
- **WHEN** raw output export is enabled
- **THEN** the workflow SHALL write a raw-output summary that includes transport, terminal adapter, planned command IDs, collected result count, and normalized output lengths

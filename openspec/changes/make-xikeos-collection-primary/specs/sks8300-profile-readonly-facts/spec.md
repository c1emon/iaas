## MODIFIED Requirements

### Requirement: SKS8300 profile-driven gather subset selection
The system SHALL prefer collection-native XikeOS facts over SKS8300 compatibility profile subset planning for normal read-only facts collection.

#### Scenario: Select default XikeOS facts through collection subsets
- **WHEN** the operator runs the read-only facts workflow without overriding read-only fact selection
- **THEN** the workflow SHALL collect the default collection-backed facts and resource subsets
- **AND** it SHALL use `c1emon.xikeos.xikeos_facts` rather than repository command-plan parsing
- **AND** it SHALL not require the operator to provide CLI command strings

#### Scenario: Select specific collection fact subsets
- **WHEN** the operator configures read-only fact subset selection
- **THEN** the workflow SHALL map supported selection to `xikeos_facts` `gather_subset` and `gather_network_resources` values
- **AND** it SHALL pass through collection-native facts instead of adapting them to the old repository `switch_facts` schema

#### Scenario: Reject unsupported collection subset
- **WHEN** the operator configures an unsupported collection-backed subset value
- **THEN** the workflow SHALL fail before collection
- **AND** the failure SHALL identify the invalid subset value

### Requirement: Thin Ansible filter facade and reusable profile core
The system SHALL avoid requiring SKS8300 profile filters in the normal read-only facts path when collection-native facts provide the canonical schema.

#### Scenario: Use collection facts directly
- **WHEN** the role needs read-only switch facts
- **THEN** it SHALL call `c1emon.xikeos.xikeos_facts` through Ansible tasks
- **AND** it SHALL expose native collection facts without requiring local parser or profile filters

#### Scenario: Limit compatibility helpers to fallback paths
- **WHEN** local SKS8300 profile utilities remain in the repository
- **THEN** they SHALL be limited to smoke, debug, migration, or explicitly documented fallback workflows
- **AND** they SHALL NOT define the normal facts schema

## REMOVED Requirements

### Requirement: Profile command planning and read-only policy
**Reason**: Normal read-only facts collection no longer builds repository command plans from a SKS8300 command catalog; it uses `xikeos_facts` collection subsets.
**Migration**: Use `xikeos_facts.gather_subset` and `xikeos_facts.gather_network_resources` for read-only fact selection. Use `xikeos_command` only for smoke/debug/fallback commands.

### Requirement: Command-level raw export policy
**Reason**: Normal facts export no longer depends on command IDs, raw stdout mapping, or profile-generated raw export plans.
**Migration**: Export collection-native facts and rely on collection redaction for returned config data. Any raw command export must be a separately documented debug workflow.

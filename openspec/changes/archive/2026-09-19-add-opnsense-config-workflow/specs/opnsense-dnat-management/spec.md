## MODIFIED Requirements

### Requirement: Explicit optional DNAT resource
The system SHALL support `dnat.yml` with an `opnsense_dnat_rules` list through an explicit DNAT validation and execution selection. Existing callers using only the four previously supported resources SHALL remain valid without a DNAT file. Unselected DNAT SHALL NOT trigger desired-file loading, credential access or writes merely because it exists. Only an explicitly invoked online configuration workflow SHALL be permitted to read necessary unselected DNAT references for its selected resource operation; such reads SHALL NOT authorize DNAT mutation.

#### Scenario: Existing caller omits DNAT
- **WHEN** an existing four-resource environment is checked or executed without selecting DNAT or invoking the new online configuration workflow
- **THEN** its existing input contract remains valid and no DNAT operation occurs

#### Scenario: Caller selects DNAT
- **WHEN** a caller selects a standard DNAT file
- **THEN** check/generate validates that file offline and only explicit direct manage-dnat.yml invocation or the formal online configuration workflow enters credentialed DNAT operations
- **AND** generation alone never writes or activates DNAT

#### Scenario: Unselected DNAT references a selected Alias deletion
- **WHEN** the explicit online workflow checks whether an Alias selected for deletion has a surviving DNAT reference
- **THEN** the necessary DNAT reference may be read and can block the deletion
- **AND** no DNAT declaration is implicitly added to the write set

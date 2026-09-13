## RENAMED Requirements

- FROM: `### Requirement: Hand-written alias desired state`
- TO: `### Requirement: Caller-authored alias desired state`

## MODIFIED Requirements

### Requirement: Caller-authored alias desired state

The system SHALL accept caller-supplied OPNsense firewall alias desired state using `opnsense_aliases`, whether hand-written or deterministically generated from caller-maintained inputs. Both forms SHALL use the same standard resource fields, validation, identity, dependency handling, incremental ownership and activation behavior. The system SHALL NOT require the generator to reside in iaas or interpret its high-level policy.

#### Scenario: Desired aliases are reviewed as source configuration
- **WHEN** an operator reviews the OPNsense alias management input
- **THEN** the aliases SHALL be traceable to caller-maintained source configuration, either explicit resource YAML or inputs used to generate the resource YAML
- **AND** generated files SHALL be reviewable without being independently hand-maintained

#### Scenario: Export artifacts are not used as the direct apply source
- **WHEN** the alias management workflow is run
- **THEN** device exports SHALL NOT be used directly as desired state without caller review and explicit conversion to the supported resource contract

#### Scenario: Caller generator supplies standard aliases
- **WHEN** a caller-owned generator supplies valid standard alias declarations, including a network group and its declared members
- **THEN** the existing alias workflow SHALL accept them through its normal source-file input and apply the same validation and dependency behavior as hand-written declarations
- **AND** omission SHALL NOT delete or disable unlisted aliases, and existing type-continuity and explicit-removal protections SHALL remain in force

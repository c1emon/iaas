## RENAMED Requirements

- FROM: `### Requirement: Hand-written filter rule desired state`
- TO: `### Requirement: Caller-authored filter rule desired state`

## MODIFIED Requirements

### Requirement: Caller-authored filter rule desired state

The system SHALL accept caller-supplied OPNsense new firewall filter-rule desired state using `opnsense_filter_rules`, whether hand-written or deterministically generated from caller-maintained inputs. Both forms SHALL use the same standard resource contract, validation, identity, incremental reconciliation and activation behavior. The system SHALL NOT require the generator to reside in iaas or interpret its high-level policy.

#### Scenario: Desired filter rules are reviewed as source configuration
- **WHEN** an operator reviews the OPNsense filter-rule management input
- **THEN** the rules SHALL be traceable to caller-maintained source configuration, either explicit resource YAML or inputs used to generate the resource YAML
- **AND** generated files SHALL be reviewable without being independently hand-maintained

#### Scenario: Export artifacts are not used as the direct apply source
- **WHEN** the filter-rule management workflow is run
- **THEN** device exports and legacy CSV exports SHALL NOT be used directly as desired state without caller review and explicit conversion to the supported resource contract

#### Scenario: Caller generator supplies standard rules
- **WHEN** a caller-owned generator supplies valid standard resource declarations
- **THEN** the existing resource workflow SHALL accept them without a generator-specific input mode or a dependency on the caller repository
- **AND** omission SHALL NOT delete or disable undeclared rules

### Requirement: Inversion-aware destination safety

Filter-rule safety checks SHALL evaluate destination inversion consistently in Python admission and Ansible before credentials or writes while retaining explicit ownership and management-access protections. An optional generic resource context SHALL allow static alias coverage of declared interface networks to inform the existing check without adding routing-policy assumptions. Insufficient evidence SHALL NOT bypass the retained protection.

#### Scenario: Caller declares an inverted destination
- **WHEN** an otherwise valid deny rule targets the inverse of its own interface network
- **THEN** the workflow SHALL NOT classify that rule as denying the uninverted interface network solely from a literal name intersection
- **AND** it SHALL preserve the caller's explicit inversion without inventing routing policy

#### Scenario: A non-inverted unsafe rule is supplied
- **WHEN** a rule violates the retained management-access protection under its actual match semantics
- **THEN** validation SHALL still reject it before writes

#### Scenario: Static alias excludes declared ingress networks
- **WHEN** a deny rule inverts one alias and valid context statically establishes coverage of the declared ingress networks for every applicable rule address family
- **THEN** the safety check SHALL account for that exclusion without a selective-proxy exception
- **AND** acceptance SHALL NOT claim that the supplied network context matches the live appliance

#### Scenario: Static exclusion evidence is insufficient
- **WHEN** a deny rule would fail the retained protection and supplied context cannot establish the required static coverage, including reliance only on dynamic members or missing applicable-family networks
- **THEN** the rule SHALL remain rejected
- **AND** callers without context SHALL retain the existing conservative safety behavior

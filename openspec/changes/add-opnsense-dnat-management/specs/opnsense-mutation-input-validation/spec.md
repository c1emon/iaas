## MODIFIED Requirements

### Requirement: Repository-owned offline OPNsense input validation
The system SHALL expose one repository-owned offline validation command for supported OPNsense alias, IP Alias VIP, PBR gateway, new filter-rule, and explicitly selected DNAT, one-to-one NAT and interface-group desired-state files. The three new resources SHALL be optional; existing four-file directory validation SHALL retain its prior required set and SHALL NOT silently enroll DNAT in execution. SNAT names remain deferred and SHALL NOT be registered as a resource in this change.

#### Scenario: Operator validates all supported OPNsense desired state
- **WHEN** an operator runs the existing directory validation command against valid four-file state
- **THEN** it SHALL validate those four files without requiring DNAT
- **AND** it SHALL exit successfully without OPNsense API access, infrastructure credentials, SSH, or mutation

#### Scenario: Default repository desired state is validated
- **WHEN** the validator checks the desired-state files committed when this change is implemented
- **THEN** those files SHALL pass without semantic coercion or automatic rewriting

#### Scenario: DNAT is explicitly selected
- **WHEN** the caller selects DNAT through the resource command or supported runtime input selection
- **THEN** it SHALL validate the concrete DNAT contract offline before any credentialed operation
- **AND** an empty DNAT list SHALL represent no desired mutations, never a request to clear appliance rules

#### Scenario: DNAT placeholder exists
- **WHEN** an existing caller retains the former empty `opnsense_dnat_rules: []` placeholder
- **THEN** it SHALL remain ignored when DNAT is not selected and SHALL validate as an empty resource when explicitly selected
- **AND** its presence or successful validation alone SHALL NOT authorize or trigger a DNAT write

## ADDED Requirements

### Requirement: NAT and interface-group whole-batch and loaded-input admission
The system SHALL validate all selected DNAT, one-to-one NAT and interface-group records before credential access or writes and revalidate actual Ansible-loaded values with the same contract. It SHALL reject unknown keys, invalid primitive types, missing required fields, duplicate identity, illegal protocol/port combinations, unsupported enums, out-of-range values and statically provable address-family conflicts. Native special address tokens and legal external aliases SHALL remain supported without claiming their live existence. Error output SHALL identify safe field paths without dumping complete input or credentials.

#### Scenario: Later record has invalid primitive type
- **WHEN** a later selected NAT or group record specifies enabled as a string or sequence as a boolean
- **THEN** the whole selected batch fails locally before credentials and before an earlier record can mutate the appliance

#### Scenario: Loaded input differs from file
- **WHEN** Ansible variable precedence substitutes invalid values after file validation
- **THEN** loaded-input validation fails before credential preflight or any mutation module

#### Scenario: Field exceeds the supported contract
- **WHEN** a record specifies a prohibited resource-specific field such as no_port_forward or an independent NAT identity override
- **THEN** admission rejects it explicitly rather than dropping it or fabricating a translation target

#### Scenario: Valid reference needs appliance resolution
- **WHEN** a syntactically valid external target alias cannot be resolved locally
- **THEN** offline validation preserves the existing unresolved-reference boundary and does not invent a value or query the device

#### Scenario: New resource selection is optional and independent
- **WHEN** a caller explicitly selects any supported DNAT, one-to-one NAT or interface-group resource
- **THEN** only selected files are required and every selected record is validated before credentials
- **AND** an empty list never means clearing undeclared appliance objects

#### Scenario: Known group deletion conflicts with selected references
- **WHEN** selected surviving filter, DNAT or one-to-one NAT declarations refer to a selected absent group
- **THEN** local validation rejects the known conflict without requiring an inventory of all appliance objects

#### Scenario: Existing filter admission receives a group reference
- **WHEN** a filter rule and optional network context refer to a native-valid mixed-case group such as Internal
- **THEN** the shared validator and loaded-value filter accept the same reference syntax without weakening deny/inversion checks or changing VIP/Gateway physical-interface validation

#### Scenario: Direct single-resource execution has limited input
- **WHEN** a direct Ansible playbook loads only its selected resource file
- **THEN** it validates that file and actual loaded values without claiming cross-file checks over absent inputs; selected multi-resource offline scenarios check known cross-resource references and native protection covers external device references

#### Scenario: Deferred SNAT selection is rejected
- **WHEN** a caller selects `snat`, `snat.yml`, or `opnsense_snat_rules` through the resource validator or runtime selection
- **THEN** selection fails as deferred/unsupported before credentials or API access, while `manage-snat.yml` and `opnsense_snat_source` remain reserved names for a later change

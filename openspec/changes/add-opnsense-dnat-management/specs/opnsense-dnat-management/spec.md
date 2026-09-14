## Purpose

Provide reusable, explicitly selected destination NAT management from caller-owned declarations, with stable resource ownership, predictable validation and activation, and a clear separation from site policy and appliance migration.

## ADDED Requirements

### Requirement: Explicit optional DNAT resource
The system SHALL support `dnat.yml` with an `opnsense_dnat_rules` list through an explicit DNAT validation and execution selection. Existing callers using only the four previously supported resources SHALL remain valid without a DNAT file. Unselected DNAT SHALL NOT trigger credential access, API reads or writes.

#### Scenario: Existing caller omits DNAT
- **WHEN** an existing four-resource environment is checked or executed without selecting DNAT
- **THEN** its existing input contract remains valid and no DNAT operation occurs

#### Scenario: Caller selects DNAT
- **WHEN** a caller selects a standard DNAT file
- **THEN** check/generate validates that file offline and only an explicit direct manage-dnat.yml Ansible invocation can enter credentialed DNAT execution; launcher apply is not added

### Requirement: Generic DNAT declaration and ownership
The system SHALL support present/absent, enabled state, sequence, interfaces, IP family, protocol, source/destination matching and ports, translation target/port, pool options, logging, tags, per-rule reflection and associated-filter mode. It SHALL use scope/slug-derived `iaas:opnsense:dnat:<scope>:<slug>` identity, reject duplicate identities and ambiguous live matches, and preserve undeclared objects. DNAT SHALL NOT accept independent description/uuid/match_fields overrides or no_port_forward in this initial contract.

#### Scenario: Sequence changes without identity changes
- **WHEN** a declared present rule changes sequence or destination while retaining scope and slug
- **THEN** the matching managed object is updated rather than implicitly creating a replacement identity

#### Scenario: Explicit deletion
- **WHEN** an absent record supplies only scope, slug and state
- **THEN** only the unambiguously matching object is deleted, and an already absent object is unchanged

#### Scenario: Unmanaged rules exist
- **WHEN** the appliance contains rules absent from the selected declaration
- **THEN** they remain untouched, regardless of similar ports, targets or names

#### Scenario: Dual-stack declaration has conflicting literal families
- **WHEN** an inet46 declaration contains conflicting address families among non-inverted literal source/destination matches and its literal translation target
- **THEN** offline and actual-loaded-input validation reject it before credentials; inverted matches and unresolved aliases are not treated as positive literal family constraints

### Requirement: Native translation-port constraints
Source and destination matching ports SHALL support the verified native ranges and port aliases. local_port SHALL accept a single numeric port, a native well-known port name or a valid port alias, and SHALL reject literal ranges unsupported by the native local-port field. Omitting local_port SHALL clear a prior translated port and preserve the packet's original destination port, not the previously saved translation setting.

#### Scenario: Literal translation-port range
- **WHEN** local_port is 8000-8010
- **THEN** offline validation rejects it even if the provider documentation describes generic port ranges

### Requirement: Native options do not imply site policy
The system SHALL require present declarations to explicitly select per-rule reflection and associated-filter mode, including explicit inheritance/manual values. It SHALL NOT change global reflection settings, synthesize site SNAT or policy routing, infer WAN-only intent, or embed caller-specific addresses. Generic valid any-destination and NAT-pass use cases SHALL remain available. With `associated_rule=rule`, the native filter rule is generated temporarily by the appliance on filter reload and has no independent UUID or persistent filter configuration; it remains owned by the DNAT association rather than independently duplicated by this workflow.

#### Scenario: Caller selects inherited reflection
- **WHEN** nat_reflection is an explicit empty string
- **THEN** the rule inherits the existing appliance behavior and no shared setting is modified

#### Scenario: Caller manages filtering separately
- **WHEN** associated_rule is an explicit empty string
- **THEN** DNAT management does not create an independent allow rule; caller-owned filter declarations determine authorization

#### Scenario: Association changes or DNAT is removed
- **WHEN** the caller changes associated-filter mode, disables the DNAT, or deletes it
- **THEN** the next native filter reload removes or regenerates the temporary associated rule according to the new mode, with no separately editable or iaas-created persistent filter object left behind

### Requirement: Controlled batch activation and failure reporting
The system SHALL save each declared change without per-item reload, activate once after successful changed reconciliation, and never activate in check mode. CRUD failure SHALL stop activation and report possible partial saved changes. Activation failure SHALL distinguish saved and running state, without claiming rollback. An explicit validated boolean force-reload option SHALL support activation recovery after an unchanged rerun.

#### Scenario: Later record fails
- **WHEN** earlier records saved successfully but a later CRUD operation fails
- **THEN** no batch activation is attempted and the result states that partial saved configuration may remain

#### Scenario: No-change recovery
- **WHEN** reconciliation reports no changes and the caller explicitly requests force reload
- **THEN** apply activates the saved configuration once, while check mode still performs no activation

### Requirement: Fixed provider and bounded compatibility claims
The runtime SHALL package a reproducibly fixed provider revision supporting the declared DNAT contract. It SHALL NOT download or upgrade provider code during execution. Software checks SHALL cover module loading, representative transformations, repeated reconciliation, deletion, association modes, check mode and failures; existing resource regression SHALL pass. Software completion SHALL NOT claim appliance write or connectivity acceptance.

#### Scenario: Provider is missing or incompatible
- **WHEN** the selected runtime cannot load the required DNAT provider contract
- **THEN** execution fails before device writes with an actionable dependency error

#### Scenario: Only offline acceptance exists
- **WHEN** software validation passes without an authorized appliance migration
- **THEN** the result records software support and explicitly leaves site deployment and connectivity unverified

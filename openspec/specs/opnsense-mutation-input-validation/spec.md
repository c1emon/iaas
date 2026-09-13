# opnsense-mutation-input-validation Specification

## Purpose
Define deterministic offline admission checks for caller-supplied OPNsense desired state so invalid input cannot reach credentialed or mutation-capable playbook steps.

## Requirements

### Requirement: Repository-owned offline OPNsense input validation
The system SHALL expose one repository-owned offline validation command for the supported OPNsense alias, IP Alias VIP, PBR gateway, and new filter-rule desired-state files.

#### Scenario: Operator validates all supported OPNsense desired state
- **WHEN** an operator runs the OPNsense input validation command against valid repository state
- **THEN** it SHALL validate all four supported mutation input files
- **AND** it SHALL exit successfully without OPNsense API access, infrastructure credentials, SSH, or mutation

#### Scenario: Default repository desired state is validated
- **WHEN** the validator checks the desired-state files committed when this change is implemented
- **THEN** those files SHALL pass without semantic coercion or automatic rewriting

#### Scenario: DNAT placeholder exists
- **WHEN** the validator discovers the current fail-closed DNAT placeholder
- **THEN** it SHALL leave DNAT outside the supported mutation-input set
- **AND** it SHALL NOT enable or imply a DNAT write path

### Requirement: Exact shape and type validation
The validator SHALL reject malformed supported desired state before any credentialed or mutation-capable operation.

#### Scenario: Desired-state document has an invalid top-level shape
- **WHEN** a supported file has an unexpected top-level key, omits its required resource list, or defines that list as a mapping, string, or other non-list value
- **THEN** validation SHALL fail with the affected file and field path

#### Scenario: Resource record has invalid keys or types
- **WHEN** a supported resource record omits a required key, includes an unknown key, or uses a parsed value type that is not allowed for the field
- **THEN** validation SHALL fail before network or credential access
- **AND** it SHALL NOT silently discard, stringify, truth-test, or otherwise coerce the invalid value

#### Scenario: Boolean field is declared as a string or number
- **WHEN** a boolean field contains a parsed string, integer, or other non-boolean value
- **THEN** validation SHALL fail rather than treating the value as truthy or falsey

### Requirement: Resource-aware OPNsense value validation
The validator SHALL apply resource-specific syntax, enum, range, and identity rules that can be proven from local desired state.

#### Scenario: Alias input is invalid
- **WHEN** an alias has an unsupported managed type or state, malformed name, invalid content shape/value for its managed type, non-boolean enabled value, or duplicate managed name
- **THEN** validation SHALL fail with resource-index and field context

#### Scenario: IP Alias VIP input is invalid
- **WHEN** a VIP has an invalid interface identifier, invalid IP-with-prefix address, unsupported state, non-boolean bind/expand value, unknown field, or duplicate module match identity
- **THEN** validation SHALL fail with resource-index and field context

#### Scenario: PBR gateway input is invalid
- **WHEN** a gateway has an invalid name/interface/IP family/address, invalid numeric bound or threshold ordering, non-boolean flag, unsupported state, duplicate module match identity, or requests `default_gw: true`
- **THEN** validation SHALL fail with resource-index and field context
- **AND** it SHALL preserve the existing boundary that this workflow cannot claim default-route ownership

#### Scenario: New filter-rule input is invalid
- **WHEN** a filter rule has an invalid generated-identity part, duplicate generated identity, unsupported state/action/direction/IP protocol, invalid interface/net/port shape or token, out-of-range sequence or port, non-boolean flag, direct description, or unknown field
- **THEN** validation SHALL fail with resource-index and field context

#### Scenario: Value requires live OPNsense resolution
- **WHEN** local syntax is valid but correctness depends on whether an interface, alias, gateway, or other object exists on the target appliance
- **THEN** offline validation SHALL NOT claim that the live reference exists
- **AND** the existing explicit online/apply workflow SHALL remain responsible for live module and API behavior

### Requirement: Validation is a pre-mutation admission gate
Every supported OPNsense mutation playbook SHALL run the shared validator before credential preflight and before any OPNsense module capable of changing state.

#### Scenario: Direct playbook execution receives invalid desired state
- **WHEN** an operator invokes a supported mutation playbook directly with invalid desired state
- **THEN** the playbook SHALL fail at the shared local validation gate
- **AND** it SHALL NOT require API credentials, contact OPNsense, invoke a mutation module, or reload configuration

#### Scenario: Local validation succeeds
- **WHEN** the shared validator accepts the desired-state file for a supported playbook
- **THEN** the playbook SHALL be permitted to continue to the separate credential preflight and existing mutation workflow
- **AND** successful local validation alone SHALL NOT authorize or claim a live apply

### Requirement: Safe validation failure reporting
Expected OPNsense input failures SHALL be concise, deterministic, and safe for local or cloud CI logs.

#### Scenario: Invalid input is reported
- **WHEN** validation rejects an expected operator-authored input error
- **THEN** it SHALL exit non-zero
- **AND** it SHALL report the resource kind, record index or identity when safe, and field path needed for correction
- **AND** it SHALL NOT print a Python traceback, complete desired-state records, API credentials, or resolved secret values

### Requirement: Provider-compatible existing resource admission

Before writes, the runtime SHALL validate every desired resource against locally provable field semantics and the pinned Collection's basic primitive constraints. Supported native source/destination inversion SHALL require exactly one target. Offline and Ansible-loaded admission SHALL agree on primitive type and inversion semantics without introducing caller-specific routing rules.

#### Scenario: A later gateway record violates a known numeric bound
- **WHEN** a desired batch includes a record such as latency_low 0, loss_high 100 or interval 10000 that the pinned 26.1.11 Collection rejects
- **THEN** the entire batch SHALL fail local validation before credentials, API access or earlier-record mutation
- **AND** Python and Ansible admission SHALL agree on supported numeric and inversion semantics

#### Scenario: Dependency constraints are refreshed
- **WHEN** the explicitly installed Collection baseline changes
- **THEN** representative boundary tests SHALL compare the accepted primitive ranges with that baseline
- **AND** the runtime SHALL NOT copy the entire server validation model or relax default-gateway ownership

#### Scenario: Inversion contains multiple targets
- **WHEN** source or destination inversion specifies more than one target
- **THEN** offline and direct-playbook validation SHALL reject the declaration before credential access or mutation
- **AND** one valid alias target SHALL remain eligible for the normal resource and safety checks

#### Scenario: Ansible preserves a valid primitive with metadata
- **WHEN** Ansible loads a valid resource whose primitive values carry engine metadata
- **THEN** the execution adapter SHALL preserve their primitive meaning and apply the same domain checks as offline validation
- **AND** string-to-number or string-to-boolean coercion and acceptance of a boolean as an integer SHALL remain prohibited

### Requirement: Type-specific extended alias validation
The offline validator SHALL accept the managed types `host`, `network`, `port`, `urltable` and `networkgroup` with exact resource-specific fields, preserving existing static-alias behavior.

#### Scenario: URL table fields are invalid
- **WHEN** URL content is empty or malformed, a present URL table lacks `updatefreq_days`, or that value is not a decimal string of at least 0.1 days with at most one fractional digit and an unchanged finite numeric round-trip through the pinned Collection
- **THEN** validation SHALL fail with field context before credentials or network access
- **AND** URL reachability and downloaded contents SHALL NOT be checked during offline validation

#### Scenario: Fields do not belong to the alias type
- **WHEN** a non-URL-table alias includes refresh fields, an unsupported type is supplied, or an unknown field is present
- **THEN** validation SHALL fail without coercion or silently discarded input
- **AND** the existing required common fields SHALL remain required, including for absent declarations

#### Scenario: A frequency would be rounded by the dependency
- **WHEN** the caller supplies a value such as `"0.01"` or `"0.15"`
- **THEN** offline validation SHALL reject it rather than allow the Collection to change the requested frequency

### Requirement: Locally provable alias reference validation
The validator SHALL validate local group dependencies while distinguishing unresolved external references from invalid local references.

#### Scenario: Local dependency is invalid
- **WHEN** a surviving present group has duplicate members, self-reference, a locally detectable cycle, a local absent member or a local non-address member
- **THEN** validation SHALL fail before credential preflight or mutation

#### Scenario: Reference is not declared locally
- **WHEN** a surviving present group member is a valid alias name but has no local declaration
- **THEN** offline validation SHALL preserve it as an unresolved external reference
- **AND** offline success SHALL NOT claim that it exists or is compatible on the appliance
- **AND** the explicit online alias workflow SHALL resolve it before writes

#### Scenario: A group and its members are all marked absent
- **WHEN** absent records have valid required field shapes and syntax
- **THEN** offline validation SHALL NOT reject them because obsolete group content references an absent or missing member
- **AND** online removal ordering SHALL be derived from live dependencies rather than caller-supplied obsolete member content

### Requirement: Generic filter resource validation context

The filter-rule document SHALL support optional `opnsense_filter_rule_context` containing only `interface_networks`, an interface-to-CIDR-list mapping, and `aliases`, standard alias declarations. The context SHALL be independent of policy or generator identity and SHALL contain no admission-bypass flag. Context shape, types, address families and local alias dependencies SHALL be validated before credentials or mutation. When corresponding declarations are also supplied in the selected input set, inconsistent context SHALL be rejected.

#### Scenario: Consistent caller-derived context
- **WHEN** the caller supplies context derived from its selected alias declarations and reviewed interface-network facts
- **THEN** validation SHALL use only statically provable address coverage for the relevant rule families
- **AND** it SHALL NOT resolve DNS, download URL tables, access the appliance or claim that the supplied facts are current on the appliance

#### Scenario: Context conflicts with selected declarations
- **WHEN** supplied context disagrees with corresponding alias or interface-network declarations available in the selected inputs
- **THEN** validation SHALL fail rather than selecting one copy by load order

#### Scenario: Context is malformed or requests a bypass
- **WHEN** context contains unknown fields, invalid CIDRs, invalid alias declarations or a flag asserting that a rule is safe
- **THEN** validation SHALL reject the document before credentials and writes

#### Scenario: An external reference is not locally declared
- **WHEN** a syntactically valid alias reference is absent from the local input set
- **THEN** the existing unresolved-external-reference and explicit online-resolution contract SHALL remain in force
- **AND** the unknown reference SHALL NOT itself count as static coverage evidence or require complete appliance inventory

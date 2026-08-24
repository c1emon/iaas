## Purpose

Define deterministic offline admission checks for hand-written OPNsense desired state so invalid input cannot reach credentialed or mutation-capable playbook steps.

## ADDED Requirements

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

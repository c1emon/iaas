## ADDED Requirements

### Requirement: Hand-written PBR gateway desired state
The system SHALL define OPNsense PBR gateway desired state from a hand-written YAML source file using the `opnsense_gateways` variable.

#### Scenario: Desired gateways are reviewed as source configuration
- **WHEN** an operator reviews the OPNsense PBR gateway management input
- **THEN** the desired gateways are represented in a repository YAML file intended for manual review and editing

#### Scenario: Export artifacts are not used as the direct apply source
- **WHEN** the PBR gateway management workflow is run
- **THEN** it reads desired gateways from the hand-written YAML source and not directly from generated export output

### Requirement: Official gateway module usage
The system SHALL manage declared OPNsense PBR gateway objects using the official `oxlorg.opnsense.gateway` module.

#### Scenario: Declared gateway is applied
- **WHEN** the operator runs the PBR gateway management workflow with a declared gateway
- **THEN** the workflow applies that gateway using `oxlorg.opnsense.gateway`

#### Scenario: Raw API calls remain out of scope
- **WHEN** the PBR gateway management workflow is used
- **THEN** it does not use raw OPNsense API calls for gateway writes

### Requirement: Explicit present and absent states
The system SHALL support explicit `present` and `absent` states for gateways declared in `opnsense_gateways`.

#### Scenario: Declared present gateway does not exist
- **WHEN** the operator runs the PBR gateway management workflow with a declared gateway using `state: present` that does not exist in OPNsense
- **THEN** the workflow creates that gateway in OPNsense

#### Scenario: Declared present gateway already exists
- **WHEN** the operator runs the PBR gateway management workflow with a declared gateway using `state: present` that already exists in OPNsense
- **THEN** the workflow updates the declared gateway fields according to the desired YAML source

#### Scenario: Declared absent gateway exists
- **WHEN** the operator runs the PBR gateway management workflow with a declared gateway using `state: absent` that exists in OPNsense
- **THEN** the workflow removes that declared gateway from OPNsense

### Requirement: Preserve unmanaged gateways
The system SHALL NOT delete, disable, or purge OPNsense gateways that are absent from `opnsense_gateways`.

#### Scenario: Unlisted gateway exists
- **WHEN** OPNsense contains a gateway that is absent from `opnsense_gateways`
- **THEN** the PBR gateway management workflow leaves that gateway present and unchanged

### Requirement: Avoid default route ownership
The system SHALL require declared PBR gateways to opt out of default gateway candidacy by setting `default_gw: false`.

#### Scenario: Declared PBR gateway sets default_gw false
- **WHEN** every declared gateway has `default_gw: false`
- **THEN** the workflow may apply the declared gateways

#### Scenario: Declared PBR gateway attempts default route ownership
- **WHEN** any declared gateway has `default_gw: true`
- **THEN** the workflow fails validation before attempting OPNsense API write calls

### Requirement: PBR gateway scope boundary
The system SHALL limit PBR gateway management to explicitly declared gateway objects and SHALL NOT manage firewall rules, NAT, static routes, gateway groups, interfaces, or VLANs.

#### Scenario: Gateway workflow is run
- **WHEN** the operator runs the PBR gateway management workflow
- **THEN** it only creates, updates, or removes declared gateway objects

#### Scenario: PBR firewall rule is needed
- **WHEN** an operator needs a FakeIP PBR firewall rule that references a declared gateway
- **THEN** that rule is handled outside the PBR gateway management workflow

### Requirement: Gateway reload after successful changes
The system SHALL reload the OPNsense gateway target after successfully applying declared gateway changes.

#### Scenario: Gateway apply changes OPNsense state
- **WHEN** the PBR gateway management workflow creates, updates, or removes a declared gateway successfully
- **THEN** the workflow reloads the OPNsense `gateway` target so the changes become active

#### Scenario: Gateway apply makes no changes
- **WHEN** the PBR gateway management workflow completes without creating, updating, or removing any declared gateway
- **THEN** the workflow does not reload the OPNsense `gateway` target

### Requirement: Safe credential handling for PBR gateway management
The system SHALL use environment-provided OPNsense API credentials for PBR gateway management and SHALL NOT store real credentials in repository files.

#### Scenario: Missing credentials fail safely
- **WHEN** the operator runs the PBR gateway management workflow without OPNsense API credentials in the environment
- **THEN** the workflow fails before attempting OPNsense API write calls and reports the missing credential requirement

#### Scenario: Repository files contain no real API credentials
- **WHEN** the PBR gateway management workflow is configured for local execution
- **THEN** repository files contain only secret references or variable lookups and not real OPNsense API key or secret values

### Requirement: PBR gateway management validation
The system SHALL include validation commands for the PBR gateway management workflow using the uv-managed Ansible toolchain.

#### Scenario: Playbook syntax is valid
- **WHEN** the operator runs the documented syntax-check command
- **THEN** Ansible validates the PBR gateway management workflow syntax successfully

#### Scenario: YAML and Ansible linting pass
- **WHEN** the operator runs the documented lint commands
- **THEN** the repository YAML and PBR gateway management workflow pass linting without errors

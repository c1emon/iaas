# opnsense-vip-management Specification

## Purpose
Define safe, additive management of OPNsense IP Alias Virtual IPs from hand-written Ansible desired state.

## Requirements

### Requirement: Hand-written VIP desired state
The system SHALL define OPNsense VIP desired state from a hand-written YAML source file using the `opnsense_vips` variable.

#### Scenario: Desired VIPs are reviewed as source configuration
- **WHEN** an operator reviews the OPNsense VIP management input
- **THEN** the desired VIPs are represented in a repository YAML file intended for manual review and editing

#### Scenario: Export artifacts are not used as the direct apply source
- **WHEN** the VIP management workflow is run
- **THEN** it reads desired VIPs from the hand-written YAML source and not directly from generated export output

### Requirement: IP Alias only VIP management
The system SHALL manage OPNsense VIPs using IP Alias mode only.

#### Scenario: Declared VIP is applied
- **WHEN** the operator runs the VIP management workflow with a declared VIP
- **THEN** the workflow applies that VIP using `mode: ipalias`

#### Scenario: Unsupported VIP modes remain out of scope
- **WHEN** the VIP management workflow is used
- **THEN** it does not configure CARP, Proxy ARP, or Other VIP modes

### Requirement: Explicit present and absent states
The system SHALL support explicit `present` and `absent` states for VIPs declared in `opnsense_vips`.

#### Scenario: Declared present VIP does not exist
- **WHEN** the operator runs the VIP management workflow with a declared IP Alias VIP using `state: present` that does not exist in OPNsense
- **THEN** the workflow creates that IP Alias VIP in OPNsense

#### Scenario: Declared present VIP already exists
- **WHEN** the operator runs the VIP management workflow with a declared IP Alias VIP using `state: present` that already exists in OPNsense
- **THEN** the workflow updates the declared VIP fields according to the desired YAML source

#### Scenario: Declared absent VIP exists
- **WHEN** the operator runs the VIP management workflow with a declared IP Alias VIP using `state: absent` that exists in OPNsense
- **THEN** the workflow removes that declared VIP from OPNsense

### Requirement: Preserve unmanaged VIPs
The system SHALL NOT delete, disable, or purge OPNsense VIPs that are absent from `opnsense_vips`.

#### Scenario: Unlisted VIP exists
- **WHEN** OPNsense contains a VIP that is absent from `opnsense_vips`
- **THEN** the VIP management workflow leaves that VIP present and unchanged

### Requirement: VIP reload after successful changes
The system SHALL activate the fixed OPNsense interface_vip target after successful declared changes and support an explicit activation-recovery retry independent of CRUD change detection.

#### Scenario: VIP apply changes OPNsense state
- **WHEN** declared create, update or removal operations complete successfully with actual changes
- **THEN** the workflow SHALL reload the interface_vip target once and report whether activation succeeded

#### Scenario: VIP apply makes no changes
- **WHEN** reconciliation makes no changes and opnsense_force_reload is false or omitted
- **THEN** the workflow SHALL NOT perform an unnecessary reload

#### Scenario: Operator retries failed activation
- **WHEN** a previous invocation saved configuration but failed activation and the caller explicitly sets opnsense_force_reload to true
- **THEN** successful admission and reconciliation SHALL reload the same fixed target even when CRUD returns no changes
- **AND** failed activation SHALL return nonzero with saved-versus-active status and retry guidance
- **AND** the workflow SHALL NOT infer rollback or successful data-plane behavior

#### Scenario: Check mode or partial CRUD failure occurs
- **WHEN** the workflow is in check mode or a declared write fails
- **THEN** it SHALL NOT activate configuration
- **AND** a write failure SHALL report that partial configuration changes may remain without claiming success

### Requirement: Safe credential handling for VIP management
The system SHALL use environment-provided OPNsense API credentials for VIP management and SHALL NOT store real credentials in repository files.

#### Scenario: Missing credentials fail safely
- **WHEN** the operator runs the VIP management workflow without OPNsense API credentials in the environment
- **THEN** the workflow fails before attempting OPNsense API write calls and reports the missing credential requirement

#### Scenario: Repository files contain no real API credentials
- **WHEN** the VIP management workflow is configured for local execution
- **THEN** repository files contain only secret references or variable lookups and not real OPNsense API key or secret values

### Requirement: VIP management validation
The system SHALL include validation commands for the VIP management workflow using the uv-managed Ansible toolchain.

#### Scenario: Playbook syntax is valid
- **WHEN** the operator runs the documented syntax-check command
- **THEN** Ansible validates the VIP management workflow syntax successfully

#### Scenario: YAML and Ansible linting pass
- **WHEN** the operator runs the documented lint commands
- **THEN** the repository YAML and VIP management workflow pass linting without errors

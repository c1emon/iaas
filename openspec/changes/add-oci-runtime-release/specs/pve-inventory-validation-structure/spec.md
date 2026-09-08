## MODIFIED Requirements

### Requirement: Modular PVE inventory validation structure
The system SHALL organize PVE inventory validation implementation into focused modules while preserving offline validation command behavior.

#### Scenario: Import concrete validation helpers
- **WHEN** Python callers need PVE inventory validation helpers
- **THEN** cluster validation helpers SHALL be importable from `iaas_automation.pve_inventory.inventory.validation.cluster`
- **AND** VM validation helpers SHALL be importable from `iaas_automation.pve_inventory.inventory.validation.vm`
- **AND** the imported functions SHALL validate the selected environment's cluster and VM source-of-truth YAML
- **AND** no `scripts` package or compatibility facade SHALL be required

#### Scenario: Keep shared validation helpers cycle-free
- **WHEN** cluster, VM, or passthrough validation code needs shared schema assertion helpers
- **THEN** the helpers SHALL be available from `iaas_automation.common.validation`
- **AND** passthrough validation SHALL NOT import helpers through a compatibility facade

#### Scenario: Preserve offline validation behavior
- **WHEN** operators run PVE inventory validation or stale-output check commands for the selected environment
- **THEN** the system SHALL produce the same successful results for equivalent valid inventory
- **AND** it SHALL continue to reject invalid inventory before generation or provisioning
- **AND** it SHALL NOT require PVE API connectivity for offline validation

#### Scenario: Preserve normalized output shape
- **WHEN** valid cluster and VM inventory is normalized for rendering
- **THEN** the normalized cluster state and VM records SHALL keep the same keys and value meanings except for explicitly approved environment-policy generalization
- **AND** generated OpenTofu variables, Ansible inventory, documentation, and template build environment SHALL remain semantically equivalent for unchanged source data

### Requirement: PVE VM inventory identifiers are downstream-safe
The system SHALL reject PVE VM inventory identifiers that are unsafe for their downstream generated uses before rendering OpenTofu variables, Ansible inventory, or generated documentation.

#### Scenario: VM name is safe for hostname-oriented use
- **WHEN** a VM declaration is validated offline
- **THEN** its `name` SHALL be a non-empty lower-case DNS-label-safe value using only letters, digits, and hyphens
- **AND** the name SHALL start and end with a letter or digit
- **AND** the name SHALL fit within a single hostname label length
- **AND** invalid values SHALL fail with context identifying the affected VM `name` field

#### Scenario: Ansible group names are safe for generated inventory
- **WHEN** a VM declaration includes `ansible_groups`
- **THEN** each group SHALL be a non-empty string using an Ansible-safe lower-case inventory group identifier format
- **AND** duplicate group values within the same VM declaration SHALL be rejected explicitly
- **AND** invalid values SHALL fail before generated Ansible inventory is accepted
- **AND** the failure SHALL identify the affected VM and `ansible_groups` field context

#### Scenario: PVE tag values are safe for provider/PVE use
- **WHEN** a VM declaration includes `tags`
- **THEN** each tag SHALL be a non-empty string using the PVE/OpenTofu-provider-safe tag token set
- **AND** tag values SHALL NOT contain whitespace or delimiter characters that would corrupt comma-joined provider inputs
- **AND** duplicate tag values within the same VM declaration SHALL be rejected explicitly
- **AND** invalid values SHALL fail before generated OpenTofu variables, PVE VM documentation, or preflight expectations are accepted
- **AND** the failure SHALL identify the affected VM and `tags` field context

#### Scenario: Current inventory remains valid under hardened rules
- **WHEN** `$ENVIRONMENT_DIR/inventory/vms.yml` is validated offline
- **THEN** VM names, Ansible groups, PVE tags, and static IPs SHALL pass the hardened rules
- **AND** generated OpenTofu variables, Ansible inventory, PVE VM documentation, and template build environment output SHALL preserve the same schemas and meanings for unchanged valid input

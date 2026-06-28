# pve-inventory-validation-structure Specification

## Purpose

Define the modular structure and compatibility boundary for PVE inventory validation code.

## Requirements

### Requirement: Modular PVE inventory validation structure
The system SHALL organize PVE inventory validation implementation into focused modules while preserving the existing public validation entrypoints.

#### Scenario: Import existing validation entrypoints
- **WHEN** Python callers import `validate_cluster` or `validate_vms` from `scripts.pve_inventory.validation`
- **THEN** the imports SHALL continue to resolve successfully
- **AND** the imported functions SHALL validate the same cluster and VM source-of-truth YAML as before the split

#### Scenario: Keep shared validation helpers cycle-free
- **WHEN** cluster, VM, or passthrough validation code needs shared schema assertion helpers
- **THEN** the helpers SHALL be available from a common validation module
- **AND** passthrough validation SHALL NOT need to import helpers through the public `validation.py` façade

#### Scenario: Preserve offline validation behavior
- **WHEN** operators run the existing PVE inventory validation or stale-output check commands
- **THEN** the system SHALL produce the same successful results for valid inventory
- **AND** it SHALL continue to reject invalid inventory before generation or provisioning
- **AND** it SHALL NOT require PVE API connectivity for offline validation

#### Scenario: Preserve normalized output shape
- **WHEN** valid cluster and VM inventory is normalized for rendering
- **THEN** the normalized cluster state and VM records SHALL keep the same keys and value meanings as before the split
- **AND** generated OpenTofu variables, Ansible inventory, documentation, and template build environment output SHALL remain unchanged for unchanged source YAML

### Requirement: Passthrough edge cases remain covered by offline validation
The system SHALL cover PVE passthrough inventory edge cases through offline validation, tests, or generated-output assertions.

#### Scenario: VM omits passthrough declarations
- **WHEN** a VM inventory record omits passthrough declarations or sets passthrough to null or an empty list
- **THEN** offline validation SHALL treat the VM as having no passthrough devices
- **AND** generated OpenTofu inputs SHALL NOT include unintended host PCI device entries for that VM

#### Scenario: Passthrough VM generated outputs are reviewed offline
- **WHEN** a VM declares valid resource-mapping based passthrough devices
- **THEN** offline validation SHALL preserve generated host PCI device assignments and flags in reviewable generated outputs
- **AND** generated OpenTofu dynamic block inputs SHALL remain stable for unchanged source YAML
- **AND** the validation SHALL NOT require live PVE PCI mapping access

#### Scenario: Passthrough VM cloud-init and Ansible inventory behavior is verified offline
- **WHEN** a passthrough VM is rendered into generated cloud-init and Ansible inventory outputs
- **THEN** offline tests or assertions SHALL verify that passthrough does not remove required generated inventory behavior
- **AND** cloud-init user-data expectations SHALL remain explicit for passthrough VMs

#### Scenario: Invalid passthrough declarations are rejected before generation
- **WHEN** passthrough declarations contain invalid mappings, duplicate device overrides, invalid `hostpci` override values, missing required flags, or more devices than OpenTofu/PVE host PCI slots support
- **THEN** offline validation SHALL fail before generation or provisioning
- **AND** it SHALL report an actionable validation error without contacting live PVE infrastructure

### Requirement: PVE inventory validation errors include field context
The system SHALL report expected PVE inventory validation failures with enough source-field context for operators to fix YAML input without reading Python tracebacks.

#### Scenario: VM static IP is malformed
- **WHEN** a VM declaration contains a `static_ip` value that cannot be parsed as an IP interface
- **THEN** offline PVE inventory validation SHALL fail before generation or provisioning
- **AND** it SHALL report the failure as a repository validation error
- **AND** the error message SHALL identify the affected VM and `static_ip` field
- **AND** the failure SHALL NOT require live PVE infrastructure access

#### Scenario: VM static IP does not match the selected network
- **WHEN** a VM declaration contains a `static_ip` whose address family, prefix length, or address range does not match the VM's selected declared network
- **THEN** offline PVE inventory validation SHALL fail before generation or provisioning
- **AND** the error message SHALL identify the affected VM and `static_ip` field or selected network context
- **AND** the failure SHALL NOT require live PVE infrastructure access

#### Scenario: VM static IP is not a usable unique host address
- **WHEN** a VM declaration contains a `static_ip` that is the selected network address, the selected network broadcast address, or duplicates another declared VM host address
- **THEN** offline PVE inventory validation SHALL fail before generation or provisioning
- **AND** the error message SHALL identify the affected VM and `static_ip` field or duplicate address context
- **AND** the failure SHALL NOT require live PVE infrastructure access

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
- **WHEN** the repository's current `inventory/vms.yml` is validated offline
- **THEN** VM names, Ansible groups, PVE tags, and static IPs SHALL pass the hardened rules
- **AND** generated OpenTofu variables, Ansible inventory, PVE VM documentation, and template build environment output SHALL preserve the same schemas and meanings for unchanged valid input

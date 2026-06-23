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

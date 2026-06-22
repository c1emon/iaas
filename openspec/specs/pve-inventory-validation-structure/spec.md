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

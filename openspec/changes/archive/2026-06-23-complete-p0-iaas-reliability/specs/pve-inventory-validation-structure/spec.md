## ADDED Requirements

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

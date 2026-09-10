## ADDED Requirements

### Requirement: Target-attributed isolated exports
OPNsense export SHALL preserve device attribution and prevent artifacts from distinct selected hosts from overwriting one another.

#### Scenario: Multiple hosts are exported
- **WHEN** more than one explicitly selected inventory host executes the export
- **THEN** each host SHALL write beneath its own safe target subdirectory
- **AND** artifact metadata SHALL identify the target
- **AND** a concurrent target SHALL NOT replace another target's files

#### Scenario: Existing consumers adopt the output layout
- **WHEN** the target-isolated export layout is introduced
- **THEN** operator documentation SHALL state the new paths and migration
- **AND** export SHALL remain read-only and SHALL NOT become an apply source

## MODIFIED Requirements

### Requirement: VMID ownership readiness
The system SHALL detect declared VMID occupancy and declaration compatibility before live plan/apply-like operations, while treating root/state ownership as a separate admission fact.

#### Scenario: Declared VMID is free
- **WHEN** PVE preflight confirms a declared VMID does not exist in the selected scope
- **THEN** it SHALL report the VMID as available
- **AND** incomplete or unauthorized observation SHALL NOT be treated as absence

#### Scenario: Declared VMID already belongs to this repository
- **WHEN** an occupied VMID matches the expected declaration and repository ownership markers
- **THEN** preflight SHALL report declaration compatibility without asserting ownership by the selected root/state
- **AND** names, tags and descriptions SHALL NOT authorize adoption, import or a second state claiming the object
- **AND** lifecycle admission SHALL still require the selected state's native association and caller-owned ownership context

#### Scenario: Declared VMID is occupied by an unexpected VM
- **WHEN** PVE preflight checks an occupied VMID not associated with the selected state, or with conflicting object identity or ownership context
- **THEN** it SHALL fail before any plan/apply-like workflow is attempted
- **AND** it SHALL report safe conflict context without changing the object

#### Scenario: A managed VM has an intended change or configuration drift
- **WHEN** the selected state's native association and caller ownership context identify the occupied VM, but its mutable name, tags or configuration differ from the desired declaration
- **THEN** readiness SHALL report the difference without treating it alone as an ownership conflict
- **AND** the complete-root native plan SHALL determine the reviewed update, replacement or deletion instead of preflight blocking legitimate drift repair
- **AND** observation without state ownership evidence SHALL remain informational rather than authorize mutation

#### Scenario: Ownership remains unknown
- **WHEN** current root/state ownership cannot be established
- **THEN** the stateful lifecycle SHALL reject mutation and require caller reconciliation
- **AND** preflight SHALL NOT infer authorization from the VMID range or a repository marker

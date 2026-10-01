## ADDED Requirements

### Requirement: Ordinary VM pool placement is explicit
Ordinary VM inventory SHALL support an optional nonempty PVE pool name and SHALL pass it to the actual OpenTofu VM resource in both protected and unprotected lifecycle branches. Omission or null SHALL mean no pool placement, independently of template membership or hidden pool defaults. IaaS SHALL use existing pools only, without creating/deleting pools or changing ACLs.

#### Scenario: Ordinary VM specifies an existing pool
- **WHEN** a VM declaration specifies an existing pool and online admission confirms the effective permissions
- **THEN** generated OpenTofu inputs and the actual VM resource SHALL preserve that exact pool and provision the VM into it
- **AND** both lifecycle branches SHALL remain in parity without changing their resource addresses

#### Scenario: Ordinary VM omits pool
- **WHEN** a VM omits pool or explicitly supplies null
- **THEN** its actual OpenTofu VM resource SHALL request no pool placement
- **AND** it SHALL NOT inherit another pool from the template or silently substitute a default

#### Scenario: A declared pool cannot be used
- **WHEN** pool is empty/invalid, nonexistent or not authorized for the actual operation
- **THEN** the workflow SHALL refuse dependent facility writes with a bounded diagnostic
- **AND** it SHALL NOT fall back to no pool or manage pool/ACL objects

## MODIFIED Requirements

### Requirement: Reserved naming and ID ranges
The system SHALL validate environment-declared PVE naming and VMID policies against generic safety constraints, including an optional dedicated acceptance VMID interval whose endpoints are inclusive. Acceptance and other declared bands SHALL NOT overlap, and ordinary VM declarations SHALL NOT use the acceptance interval.

#### Scenario: Reserve VM ID ranges
- **WHEN** environment inventory defines template, long-lived, and ephemeral/lab VMID bands
- **THEN** each band SHALL be well formed, non-overlapping, and within generic PVE/provider safety limits
- **AND** VMs and templates SHALL use the band matching their declared lifecycle
- **AND** destructive wrappers SHALL enforce absolute protection limits in addition to environment policy

#### Scenario: Name templates safely and predictably
- **WHEN** an environment declares a reusable template
- **THEN** the name SHALL use a validated conservative PVE-safe pattern
- **AND** date or version naming MAY be declared by environment policy
- **AND** automation SHALL NOT require an environment-specific template name

#### Scenario: Reserve an acceptance interval
- **WHEN** the caller declares acceptance=[500,550] and ephemeral_lab=[551,800]
- **THEN** both endpoints of each interval SHALL be included, ordinary VMIDs in [500,550] SHALL be rejected, and the applicable ordinary lifecycle rules SHALL continue to apply
- **AND** these values SHALL be caller configuration, not hard-coded reusable defaults

#### Scenario: Acceptance interval is malformed or overlaps another band
- **WHEN** any bound is invalid or the acceptance interval overlaps a declared template/ordinary interval
- **THEN** offline validation SHALL fail without credentials or network access
- **AND** successful normalization/rendering SHALL preserve the exact declared policy for subsequent plan binding

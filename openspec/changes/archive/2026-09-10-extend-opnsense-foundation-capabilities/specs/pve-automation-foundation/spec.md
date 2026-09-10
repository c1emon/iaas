## ADDED Requirements

### Requirement: Ordered current-input PVE lifecycle execution
PVE planning and apply SHALL use current generated inputs and SHALL preserve required execution order independently of caller working directory and Make parallelism.

#### Scenario: Caller enables parallel Make
- **WHEN** apply executes with parallel MAKEFLAGS
- **THEN** rendering SHALL finish before upload, upload before remote verification, and verification before OpenTofu apply
- **AND** failure of any phase SHALL stop dependent phases

#### Scenario: Generated inputs are stale
- **WHEN** plan or apply inputs no longer match the selected authored inventory
- **THEN** the workflow SHALL fail before remote writes or lifecycle execution
- **AND** it SHALL NOT silently regenerate caller-authored configuration

### Requirement: Cloud-init consumption is bound to the current source
Upload and verification SHALL compare the explicit current tfvars input with the source hash already recorded in the rendered manifest before any SSH call.

#### Scenario: Source is missing or different
- **WHEN** current tfvars are missing, unreadable or differ from the manifest source hash
- **THEN** upload and verification SHALL fail before SSH even if all snippet checksums match the old manifest

#### Scenario: Exact rendered artifacts are consumed
- **WHEN** source and snippet checksums match
- **THEN** upload and verification SHALL use those artifacts without rerendering
- **AND** existing restrictive handling of cloud-init secrets SHALL remain in force

### Requirement: Authoritative snippet storage resolution
The privileged snippet wrapper SHALL use an authoritative PVE storage path and SHALL NOT guess a destination after resolution failure.

#### Scenario: Storage resolution fails
- **WHEN** pvesm cannot resolve the requested snippet volume
- **THEN** upload SHALL fail before creating directories or installing files
- **AND** verification SHALL fail without checking a fabricated fallback path

#### Scenario: Storage path is valid
- **WHEN** PVE resolves the explicit storage and safe snippet name
- **THEN** the wrapper SHALL retain existing path, filename, checksum and storage-permission protections

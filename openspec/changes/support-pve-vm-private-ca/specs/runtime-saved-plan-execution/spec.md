## ADDED Requirements

### Requirement: PVE provider and API operations share effective TLS trust
PVE VM planning and saved-plan execution SHALL use the same effective private CA selection and insecure mode for PVE API checks and the OpenTofu provider. Private CA use SHALL preserve system public roots and SHALL NOT disable verification for unrelated HTTPS connections.

#### Scenario: Plan and apply use strict private trust
- **WHEN** a VM plan or its saved apply uses a private CA with `pve.insecure: false`
- **THEN** PVE API operations and the provider SHALL both use that private CA together with system public roots
- **AND** both SHALL reject untrusted, out-of-validity or endpoint-mismatching certificates without insecure fallback
- **AND** caller-selected backend TLS and AWS CA settings SHALL retain their existing meaning

#### Scenario: Provider honors explicit insecure mode
- **WHEN** the reviewed target has `pve.insecure: true`, even with a supplied CA
- **THEN** PVE API operations and the provider SHALL both skip certificate verification
- **AND** parsing or validating unused CA contents SHALL NOT become an execution prerequisite

### Requirement: Effective private CA travels with the saved plan
When strict VM planning uses a private CA, the runtime SHALL preserve the exact CA bytes used by planning as controlled companion material, associated with the selected native plan and checked for consistency. Saved apply and independent verify SHALL restore this material without depending on the original Runner path.

#### Scenario: Freeze the CA actually used for planning
- **WHEN** a strict VM plan is prepared with `files.api_ca`
- **THEN** planning SHALL use a task-owned copy for both PVE API access and the provider
- **AND** the completed plan SHALL retain that copy, its bundle-relative location and content digest in the existing companion contract
- **AND** it SHALL NOT freeze a Runner-specific absolute trust path into the native plan

#### Scenario: Execute or verify on another Runner
- **WHEN** matching saved-plan materials are transferred to another task or Runner and the original CA source path is unavailable
- **THEN** apply and independent verify SHALL restore the saved CA before PVE API access, and apply SHALL use it for the provider
- **AND** a current environment CA SHALL NOT replace or become an additional prerequisite for that saved trust

#### Scenario: Server certificate is renewed under the saved CA
- **WHEN** the server presents a renewed certificate that is currently valid, matches the endpoint and chains to the saved trust
- **THEN** certificate renewal alone SHALL NOT require a new plan or a leaf-certificate fingerprint update
- **AND** TLS verification SHALL use the certificate presented at execution time

#### Scenario: Required CA material is missing or changed
- **WHEN** a plan declares private CA material but its saved file is missing, escapes the companion directory or does not match its recorded digest
- **THEN** admission SHALL fail before PVE API access, backend initialization, snippet upload or VM changes
- **AND** it SHALL NOT substitute a current CA, downgrade to system-only trust, enable insecure or silently replan

#### Scenario: Plan has no effective private CA
- **WHEN** a plan uses system-only trust or explicit insecure mode
- **THEN** no CA companion SHALL be required and a supplied but unused CA SHALL NOT be frozen as an execution prerequisite
- **AND** existing plan version, runtime and target checks SHALL remain in force without an additional CA migration requirement

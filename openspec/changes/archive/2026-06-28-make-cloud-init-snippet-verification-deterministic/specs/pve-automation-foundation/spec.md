## ADDED Requirements

### Requirement: Runtime cloud-init snippets are exact verified artifacts
The system SHALL render runtime cloud-init user-data snippets into local artifacts and verify that uploaded PVE snippets match those exact artifacts by checksum.

#### Scenario: Render snippets for an operation
- **WHEN** an operator renders runtime cloud-init user-data snippets for declared PVE VMs
- **THEN** the system SHALL write one user-data file per declared VM to the ignored cloud-init cache directory
- **AND** it SHALL write a manifest describing each rendered snippet file, VM identity, storage file ID, byte count, and SHA-256 checksum
- **AND** it SHALL treat the rendered files and manifest as the source of truth for later upload and verify steps in that operation
- **AND** it SHALL NOT write plaintext passwords, private keys, or token secrets into committed generated files

#### Scenario: Upload snippets from rendered artifacts
- **WHEN** an operator uploads runtime cloud-init snippets
- **THEN** the system SHALL upload the exact snippet file contents recorded in the local manifest
- **AND** it SHALL NOT implicitly re-render snippet content during upload
- **AND** it SHALL use the audited PVE host-side snippet wrapper rather than a broad remote install command

#### Scenario: Verify remote snippets by checksum
- **WHEN** an operator verifies runtime cloud-init snippets on a PVE node
- **THEN** the system SHALL compare each remote snippet with the SHA-256 checksum recorded in the local manifest
- **AND** verification SHALL fail when remote content differs from the manifest checksum, even if the remote file exists and contains valid YAML
- **AND** verification SHALL report which snippet failed without printing plaintext secrets, password hashes, private keys, or token material

#### Scenario: Preserve password hash runtime behavior
- **WHEN** runtime cloud-init snippets are rendered in separate operations
- **THEN** password hashes MAY differ because runtime password hashing may use fresh salt
- **AND** the system SHALL NOT require fixed long-lived salts or cross-operation password hash determinism
- **AND** upload and verify determinism SHALL be scoped to the exact artifacts rendered for the current operation

### Requirement: Runtime cloud-init SSH operations are bounded
The system SHALL bound SSH subprocesses used for runtime cloud-init upload and verification.

#### Scenario: SSH upload or verify hangs
- **WHEN** a cloud-init upload or verify SSH subprocess exceeds the configured timeout
- **THEN** the command SHALL fail with an operator-readable error
- **AND** it SHALL NOT hang indefinitely
- **AND** it SHALL NOT disclose runtime secret values in the timeout error

### Requirement: PVE snippet wrapper supports checksum verification
The PVE host-side snippet wrapper SHALL support verifying stored snippet content against an expected SHA-256 checksum.

#### Scenario: Wrapper verifies matching checksum
- **WHEN** the wrapper is invoked for an existing snippet with verify mode and the expected SHA-256 checksum
- **THEN** it SHALL read the stored snippet from the constrained storage path
- **AND** it SHALL exit successfully when the stored content checksum matches the expected value

#### Scenario: Wrapper detects checksum mismatch
- **WHEN** the wrapper is invoked for an existing snippet with verify mode and an expected SHA-256 checksum that does not match the stored content
- **THEN** it SHALL fail with an operator-readable checksum mismatch error
- **AND** it SHALL NOT rewrite, delete, or otherwise mutate the stored snippet during verification

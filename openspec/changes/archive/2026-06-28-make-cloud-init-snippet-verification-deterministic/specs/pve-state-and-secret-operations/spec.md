## ADDED Requirements

### Requirement: Cloud-init manifests remain local runtime artifacts
The system SHALL treat cloud-init snippet manifests and checksums as ignored runtime artifacts adjacent to rendered user-data snippets.

#### Scenario: Operator reviews cloud-init runtime cache contents
- **WHEN** an operator inspects the cloud-init runtime cache directory
- **THEN** documentation SHALL identify rendered user-data snippets and manifest/checksum files as ignored local runtime artifacts
- **AND** it SHALL state that these files must not be committed
- **AND** it SHALL explain that rendered snippets may include password hashes, SSH public keys, hostnames, IPs, and user-data content

#### Scenario: Repository review checks cloud-init manifests
- **WHEN** repository status or hygiene checks are reviewed before committing
- **THEN** tracked cloud-init rendered snippets, manifests, or checksum files under the runtime cache SHALL be treated as repository hygiene failures unless explicitly documented as safe committed artifacts
- **AND** ignored local copies SHALL remain local operator responsibility rather than being deleted automatically

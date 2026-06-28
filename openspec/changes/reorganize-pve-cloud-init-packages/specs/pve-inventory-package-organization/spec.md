## ADDED Requirements

### Requirement: Cloud-init helpers are grouped by responsibility
The system SHALL allow PVE cloud-init helper internals to be organized into responsibility-oriented modules while preserving the stable cloud-init command facade and generated output behavior.

#### Scenario: Cloud-init command facade remains stable
- **WHEN** an operator or Makefile invokes the existing cloud-init helper command through `scripts.pve_inventory.cloud_init`
- **THEN** the command-facing module entrypoint SHALL remain available without requiring command target changes
- **AND** render, upload, and verify subcommands SHALL preserve their existing argument semantics and exit behavior

#### Scenario: Cloud-init rendering behavior is preserved
- **WHEN** cloud-init rendering internals are moved into helper modules
- **THEN** generated user-data content, snippet file names, file IDs, byte counts, hashes, and manifest fields SHALL remain unchanged unless a separate explicit change modifies them
- **AND** password hashing and secret-derived values SHALL continue to be handled without exposing resolved secret values in operator-facing errors

#### Scenario: Cloud-init upload and verify behavior is preserved
- **WHEN** cloud-init upload or verification helpers are reorganized
- **THEN** SSH timeout handling, remote path construction, upload command behavior, verification command behavior, and failure reporting SHALL remain unchanged
- **AND** default offline validation SHALL NOT require PVE SSH access, runtime secrets, or mutation-capable infrastructure credentials

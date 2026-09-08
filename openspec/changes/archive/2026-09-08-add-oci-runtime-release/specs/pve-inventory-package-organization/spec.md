## MODIFIED Requirements

### Requirement: Cloud-init helpers are grouped by responsibility
The system SHALL organize PVE cloud-init helper internals into responsibility-oriented modules under `iaas_automation.pve_inventory` while preserving the canonical cloud-init command behavior.

#### Scenario: Cloud-init command facade remains stable
- **WHEN** an operator or root Makefile target invokes cloud-init behavior through `iaas_automation.pve_inventory.cloud_init`
- **THEN** render, upload, and verify subcommands SHALL preserve their documented argument and exit semantics
- **AND** environment source and existing operational paths needed by the command SHALL be passed explicitly

#### Scenario: Cloud-init rendering behavior is preserved
- **WHEN** cloud-init rendering internals are moved into helper modules
- **THEN** generated user-data content, snippet file names, file IDs, byte counts, hashes, and manifest fields SHALL remain unchanged except for updated provenance paths
- **AND** password hashing and secret-derived values SHALL remain absent from operator-facing errors and tracked generated files

#### Scenario: Cloud-init upload and verify behavior is preserved
- **WHEN** cloud-init upload or verification helpers are reorganized
- **THEN** SSH timeout handling, remote path construction, upload behavior, verification behavior, and failure reporting SHALL preserve their safety semantics
- **AND** default offline validation SHALL NOT require PVE SSH access, runtime secrets, or mutation-capable credentials

### Requirement: Offline inventory helpers are grouped by responsibility
The system SHALL organize offline PVE inventory model, rendering, and validation helpers under `iaas_automation.pve_inventory.inventory` rather than a flat or compatibility package.

#### Scenario: Inventory core helpers are organized separately from command facades
- **WHEN** maintainers inspect PVE inventory generation internals
- **THEN** model assembly, rendering, cluster validation, VM validation, and passthrough validation SHALL be grouped under `iaas_automation.pve_inventory.inventory`
- **AND** the canonical `iaas_automation.pve_inventory.cli` entrypoint SHALL receive environment source and output paths explicitly

#### Scenario: Offline inventory organization stays separate from online runtime boundaries
- **WHEN** maintainers inspect PVE online API/runtime helpers
- **THEN** transport, runtime, error, and protocol concerns SHALL remain under `iaas_automation.pve_inventory.pve_api`
- **AND** online check helpers SHALL remain separate from offline inventory model and rendering helpers

#### Scenario: Validation helpers use concrete package paths
- **WHEN** repository code or tests need PVE inventory validation helpers
- **THEN** cluster validation SHALL be imported from `iaas_automation.pve_inventory.inventory.validation.cluster`
- **AND** VM validation SHALL be imported from `iaas_automation.pve_inventory.inventory.validation.vm`
- **AND** no `scripts` or top-level validation compatibility facade SHALL be required

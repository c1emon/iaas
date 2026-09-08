# pve-inventory-package-organization Specification

## Purpose

Define internal package organization and stable public entrypoint expectations for repository-owned PVE inventory tooling.

## Requirements

### Requirement: Stable PVE inventory command facades
The system SHALL provide one supported PVE inventory command surface under `iaas_automation.pve_inventory` after the hard cutover.

#### Scenario: Existing PVE commands run after package reorganization
- **WHEN** an operator, Makefile target, or test invokes PVE generation, validation, cloud-init rendering/upload/verification, preflight, or health behavior
- **THEN** it SHALL use the documented `iaas_automation.pve_inventory.*` module entrypoint
- **AND** command arguments, exit behavior, safety class, and generated semantics SHALL remain stable except for updated repository paths
- **AND** no `scripts.pve_inventory.*` forwarding entrypoint SHALL remain

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

### Requirement: Online check helpers are grouped by responsibility
The system SHALL organize PVE online-check helper code under responsibility-oriented packages rather than a flat collection of preflight and health helper modules.

#### Scenario: Preflight helper code is organized under online checks
- **WHEN** maintainers inspect PVE preflight implementation helpers
- **THEN** API-backed readiness checks, derived preflight expectations, optional SSH adjunct checks, and shared check reporting SHALL be grouped under a check-oriented package structure
- **AND** PVE API transport/runtime concerns SHALL remain in the existing `pve_api` package rather than being duplicated in check helpers

#### Scenario: Health helper code stays separate from readiness semantics
- **WHEN** maintainers inspect PVE health implementation helpers
- **THEN** health current-state logic SHALL remain separate from preflight apply-readiness logic
- **AND** shared check/reporting primitives MAY be reused without merging the two command semantics

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

### Requirement: Package refactor preserves offline-safe validation
The system SHALL keep package reorganization from widening validation or live-access behavior.

#### Scenario: Default offline validation runs after package reorganization
- **WHEN** an operator or CI runs the aggregate offline gate
- **THEN** PVE preflight, health, planning, and mutation SHALL remain outside that gate
- **AND** the gate SHALL remain runnable without PVE API, SSH, runtime secrets, or mutation-capable credentials

#### Scenario: Tests cover moved import boundaries
- **WHEN** modules move to `automation/src/iaas_automation/`
- **THEN** tests SHALL cover canonical command facades, direct supported imports, explicit path injection, and moved helper behavior
- **AND** the old `scripts` package, thin compatibility wrappers, and aliases SHALL NOT remain

### Requirement: Health check helpers are grouped under health checks
The system SHALL organize PVE health current-state helpers under `iaas_automation.pve_inventory.checks.health` while preserving the canonical health command.

#### Scenario: Health internals are separate from the command facade
- **WHEN** maintainers inspect PVE health implementation internals
- **THEN** expectation derivation and current-state checks SHALL be grouped under `iaas_automation.pve_inventory.checks.health`
- **AND** `iaas_automation.pve_inventory.health` SHALL be the sole command-facing module entrypoint

#### Scenario: Health and preflight semantics stay separate
- **WHEN** health internals are moved under check-oriented packages
- **THEN** health current-state checks SHALL remain separate from preflight apply-readiness checks
- **AND** shared result/reporting primitives MAY be reused without merging command semantics

#### Scenario: Health behavior is preserved during reorganization
- **WHEN** an operator or test invokes PVE health after migration
- **THEN** result IDs, severity semantics, runtime parsing, report output, and exit behavior SHALL remain unchanged
- **AND** transport/runtime/error concerns SHALL remain in `iaas_automation.pve_inventory.pve_api`

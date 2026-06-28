# pve-inventory-package-organization Specification

## Purpose

Define internal package organization and stable public entrypoint expectations for repository-owned PVE inventory tooling.

## Requirements

### Requirement: Stable PVE inventory command facades
The system SHALL preserve stable command-facing module entrypoints while allowing internal helper modules to be reorganized into subpackages.

#### Scenario: Existing PVE commands run after package reorganization
- **WHEN** an operator or Makefile invokes PVE inventory generation, PVE preflight, PVE health, or cloud-init helper commands through the existing repository module entrypoints
- **THEN** those entrypoints SHALL remain available without requiring command target changes
- **AND** generated outputs, check reports, exit-code semantics, and required runtime context SHALL remain unchanged unless a separate explicit change modifies them

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
The system SHALL organize offline PVE inventory model, rendering, and validation helper code under an inventory-oriented package structure rather than a flat collection of top-level helper modules.

#### Scenario: Inventory core helpers are organized separately from command facades
- **WHEN** maintainers inspect PVE inventory generation internals
- **THEN** model assembly, output rendering, cluster validation, VM validation, and passthrough validation helpers SHALL be grouped under an inventory-oriented package
- **AND** stable command-facing entrypoints such as `scripts.pve_inventory.cli` SHALL remain available without requiring Makefile or operator command target changes

#### Scenario: Offline inventory organization stays separate from online runtime boundaries
- **WHEN** maintainers inspect PVE online API/runtime helpers after the inventory core is reorganized
- **THEN** PVE API transport/runtime/error/protocol concerns SHALL remain in the existing `pve_api` package rather than moving under the offline inventory package
- **AND** online check helpers SHALL remain under check-oriented packages rather than being merged into offline inventory model or rendering helpers

#### Scenario: Top-level validation facade remains stable
- **WHEN** repository tests or callers intentionally import validation helpers from `scripts.pve_inventory.validation`
- **THEN** that validation facade SHALL continue to expose the stable validation helpers needed by existing commands and tests
- **AND** moved internal validation implementation modules SHALL NOT require callers to import from obsolete top-level helper paths

### Requirement: Package refactor preserves offline-safe validation
The system SHALL keep package reorganization as an internal refactor that does not widen validation or live-access behavior.

#### Scenario: Default offline validation runs after package reorganization
- **WHEN** an operator or CI runs the repository's default offline validation gate
- **THEN** PVE online preflight and PVE health SHALL remain outside that default gate
- **AND** the default gate SHALL remain runnable without PVE API access, SSH access, 1Password access, runtime secrets, or mutation-capable infrastructure credentials

#### Scenario: Tests cover moved import boundaries
- **WHEN** internal PVE inventory modules are moved into subpackages
- **THEN** repository tests SHALL cover the command facades and moved helper behavior sufficiently to detect broken imports or behavior drift
- **AND** obsolete thin compatibility wrappers SHOULD NOT be kept unless they protect a documented command or import surface

### Requirement: Health check helpers are grouped under health checks
The system SHALL organize PVE health current-state implementation helpers under a health-oriented check package while preserving the stable top-level health command facade.

#### Scenario: Health internals are separate from the command facade
- **WHEN** maintainers inspect PVE health implementation internals
- **THEN** expectation derivation and health current-state check helpers SHALL be grouped under `scripts.pve_inventory.checks.health` or equivalent health-oriented check modules
- **AND** `scripts.pve_inventory.health` SHALL remain available as the stable command-facing module entrypoint

#### Scenario: Health and preflight semantics stay separate
- **WHEN** health internals are moved under check-oriented packages
- **THEN** health current-state checks SHALL remain separate from preflight apply-readiness checks
- **AND** shared result/reporting primitives MAY be reused without merging health and preflight command semantics

#### Scenario: Health behavior is preserved during reorganization
- **WHEN** an operator or test invokes PVE health after helper reorganization
- **THEN** health result IDs, severity semantics, runtime parsing, report output, and exit-code behavior SHALL remain unchanged
- **AND** PVE API transport/runtime/error concerns SHALL remain in the shared `pve_api` package rather than being duplicated in health helper modules

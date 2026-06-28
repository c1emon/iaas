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

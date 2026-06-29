## ADDED Requirements

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

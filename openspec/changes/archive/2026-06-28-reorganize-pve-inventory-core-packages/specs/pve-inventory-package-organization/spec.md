## ADDED Requirements

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

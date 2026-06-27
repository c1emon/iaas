# iaas-repository-hygiene Specification

## Purpose

Define repository hygiene expectations for supported scripts and for human architecture documentation staying aligned with source-of-truth inventory facts.

## Requirements

### Requirement: Supported repository scripts remain runnable or are retired
The system SHALL not retain broken legacy scripts as supported repository entrypoints.

#### Scenario: Legacy script imports removed modules
- **WHEN** a repository script imports modules that no longer exist in the current source tree
- **THEN** the script SHALL be repaired, removed, or explicitly archived as unsupported legacy material
- **AND** current Makefile targets, tests, and operator docs SHALL NOT instruct operators to run that broken script as a supported workflow

### Requirement: Human architecture documentation follows source-of-truth facts
Human-maintained architecture documentation SHALL not contradict current source-of-truth inventory for concrete PVE node facts.

#### Scenario: PVE node facts are documented
- **WHEN** architecture documentation states concrete PVE node facts such as node names, management addresses, or roles
- **THEN** those facts SHALL match the current inventory source of truth or be explicitly marked as historical/uncertain
- **AND** known contradictions between `docs/architecture.md` and `inventory/pve-cluster.yml` SHALL be corrected as documentation hygiene issues

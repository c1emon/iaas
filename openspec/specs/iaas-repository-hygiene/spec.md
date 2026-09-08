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
Current human-maintained architecture documentation SHALL not contradict the selected environment's authoritative authored facts.

#### Scenario: PVE node facts are documented
- **WHEN** current architecture documentation states concrete PVE node facts such as node names, management addresses, or roles
- **THEN** those facts SHALL match `$ENVIRONMENT_DIR/inventory/pve-cluster.yml` or be explicitly marked historical/uncertain
- **AND** current documentation SHALL be corrected when it conflicts with selected environment inventory

#### Scenario: Historical documentation records an old path or fact
- **WHEN** an immutable OpenSpec archive or prominently labeled historical decision records its original context
- **THEN** it MAY retain old paths or superseded facts as historical evidence
- **AND** it SHALL NOT be presented as the current operator source of truth

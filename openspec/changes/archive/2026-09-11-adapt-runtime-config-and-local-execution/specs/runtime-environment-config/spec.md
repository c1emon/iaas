## Purpose

Define caller-owned environment configuration, bounded shared-fact references and component selection that preserve existing domain rules independently of runtime directory layout.

## ADDED Requirements

### Requirement: Versioned environment entrypoint
The runtime SHALL accept a versioned caller-owned environment entrypoint locating facility-oriented component inputs independently of its internal Ansible and inventory layout.

#### Scenario: Equivalent input layouts
- **WHEN** equivalent valid component inputs are selected through entrypoints in two different directory layouts
- **THEN** validation and generation SHALL have equivalent domain semantics
- **AND** the runtime SHALL reuse the existing component schemas and invariants without requiring the caller to author the generated Ansible layout

#### Scenario: Unsupported or legacy format
- **WHEN** the new entrypoint receives a missing or unsupported schema version
- **THEN** it SHALL fail with explicit format or migration guidance before generation or online access
- **AND** existing documented directory/file entrypoints SHALL retain their explicit behavior without automatic source rewrites or format guessing

### Requirement: Bounded shared facts
The runtime SHALL resolve explicit typed references to shared facts without executing scripts, evaluating templates, or merging fields solely because their values are equal.

#### Scenario: Reuse a declared fact
- **WHEN** selected components reference the same declared address or network fact
- **THEN** the fact SHALL be maintained once and resolved into the consuming component inputs
- **AND** semantically independent management, probe and gateway fields SHALL remain independently declarable

#### Scenario: Invalid reachable reference
- **WHEN** a selected input contains a missing, cyclic or type-incompatible reference
- **THEN** validation SHALL identify the failing logical reference and stop before output generation or online access
- **AND** errors SHALL NOT expose secret values

### Requirement: Scenario and component isolation
The runtime SHALL process only the explicitly selected scenario or documented daily default, selected components and their necessary input dependencies.

#### Scenario: Choose one scenario
- **WHEN** an operator selects a known scenario
- **THEN** unselected scenarios SHALL NOT participate in generation or execution
- **AND** selecting a test scenario SHALL NOT overwrite the authored daily-default inputs
- **AND** an unknown scenario SHALL fail without falling back to the default

#### Scenario: Operate one component
- **WHEN** an operator selects OPNsense without any PVE or K3s dependency
- **THEN** the operation SHALL NOT require PVE, K3s or S3 inputs
- **AND** reading necessary shared facts SHALL NOT execute dependent components or expand the device mutation scope

#### Scenario: Domain requires a complete scope
- **WHEN** a requested partial scope violates a component's complete-root or whole-cluster rule
- **THEN** the runtime SHALL reject it with the required scope explained
- **AND** it SHALL NOT silently select more devices or remove declarations from a shared OpenTofu root to imitate a scoped apply

### Requirement: Portable input paths and output protection
Configuration-relative paths SHALL resolve against the declaring file; all resolved source inputs and implementation resources SHALL be protected from output overlap.

#### Scenario: Invoke from another working directory
- **WHEN** the same configuration is selected from a different client working directory or transferred to DinD
- **THEN** its declared references SHALL still resolve to the same selected input contents
- **AND** explicit external files SHALL be mapped deliberately rather than interpreted as daemon-host paths

#### Scenario: Unsafe or unavailable paths
- **WHEN** an output overlaps a resolved source, a symlink resolves outside an allowed supplied mapping, or an explicit external file cannot be provided
- **THEN** the runtime SHALL fail before writing outputs or accessing infrastructure
- **AND** it SHALL NOT guess a replacement path or overwrite authored inputs

### Requirement: Caller source remains authoritative
Compilation and explicit generated-output export SHALL preserve caller-authored configuration and existing resource identities.

#### Scenario: Generate or export selected outputs
- **WHEN** an operator generates or explicitly exports a component's non-sensitive derived files
- **THEN** only the selected outputs SHALL be written to the declared safe destination
- **AND** no second handwritten source, source rewrite, automatic Git commit, resource-address change or state migration SHALL be introduced

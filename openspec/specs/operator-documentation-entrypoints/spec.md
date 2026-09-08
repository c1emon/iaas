# operator-documentation-entrypoints Specification

## Purpose

Define the human-facing documentation entrypoints and layering for safe repository operation.

## Requirements

### Requirement: Root README operator manual
The repository root `README.md` SHALL serve as the primary operator manual for human readers.

#### Scenario: Operator opens the repository
- **WHEN** an operator opens the root README
- **THEN** the README SHALL explain what the repository manages
- **AND** it SHALL point to the main capability areas and detailed documentation
- **AND** it SHALL not require the reader to inspect multiple module README files before understanding the safe starting point

#### Scenario: Operator needs safe first commands
- **WHEN** an operator wants to validate the repository without live infrastructure access
- **THEN** the root README SHALL identify offline-safe validation and generation workflows
- **AND** it SHALL distinguish those workflows from online or mutation-capable commands

### Requirement: Documentation safety model
The operator documentation SHALL classify commands and workflows by operational risk.

#### Scenario: Documentation lists common commands
- **WHEN** the root README lists common workflows or command examples
- **THEN** it SHALL identify whether the workflow is offline-safe, online read-only, or mutation-capable
- **AND** mutation-capable examples SHALL be presented only after the safety model is introduced

#### Scenario: Documentation describes default validation
- **WHEN** the root README describes default validation
- **THEN** it SHALL state that the default offline gate does not require runtime secrets or live PVE, OPNsense, switch, guest, Packer build, OpenTofu apply/destroy, or Ansible mutation access

### Requirement: Source-of-truth and generated-output map
The operator documentation SHALL identify explicitly selected environment sources, their authority boundaries, and committed generated outputs.

#### Scenario: Operator edits inventory
- **WHEN** an operator wants to change declared infrastructure, service, foundation, or device metadata
- **THEN** the root README SHALL identify the generic environment directory contract and its `inventory/` and `ansible/` inputs through the canonical operator documentation
- **AND** it SHALL identify the PVE cluster and VM inventories as authoritative for PVE topology and VM lifecycle facts
- **AND** it SHALL direct the operator to the existing generation and stale-output check workflows

#### Scenario: Operator reviews generated files
- **WHEN** generated outputs are documented
- **THEN** the root README SHALL identify the selected generated-output directory and which non-sensitive artifacts an environment repository may commit
- **AND** detailed state, cache, and observation handling SHALL be linked rather than duplicated

#### Scenario: Operator migrates an environment-specific invocation
- **WHEN** a supported runtime example previously relied on an Astra selector or default path
- **THEN** current documentation SHALL show the generic explicit environment/output inputs and changed helper names
- **AND** actual environment data and execution records SHALL be maintained by callers outside the runtime repository
- **AND** host helper migration SHALL retain its explicit online authorization boundary

### Requirement: Runtime parameter and secret guidance
The operator documentation SHALL summarize runtime parameters and secret-injection conventions.

#### Scenario: Operator runs a credentialed workflow
- **WHEN** a command requires PVE, OPNsense, switch, guest, or SSH runtime context
- **THEN** the root README SHALL describe the relevant environment-template or runtime-injection convention at a summary level
- **AND** it SHALL link to detailed module/runbook documentation for exact workflow requirements

#### Scenario: Operator reviews sensitive paths
- **WHEN** documentation discusses state, cache, exports, generated snippets, or resolved credentials
- **THEN** it SHALL direct readers to the state/cache/secret operations runbook
- **AND** it SHALL not imply that resolved secrets, private keys, local state, cache files, or raw exports are safe to commit

### Requirement: Documentation index
The `docs/README.md` file SHALL function as a documentation index rather than a minimal placeholder.

#### Scenario: Reader enters docs directory
- **WHEN** a reader opens `docs/README.md`
- **THEN** it SHALL group documentation by reader intent, such as planning, architecture, operations/runbooks, PVE, OPNsense, switches, service metadata, generated references, decisions, and historical context
- **AND** it SHALL point back to the root README as the start-here operator manual

#### Scenario: Reader looks for current roadmap
- **WHEN** a reader looks for planning status from `docs/README.md`
- **THEN** the docs index SHALL point to the current roadmap entrypoint provided by the roadmap consolidation change
- **AND** historical roadmap or research documents SHALL be labeled as historical or contextual when linked

### Requirement: Documentation layering
The documentation SHALL keep global operator guidance, detailed docs, and module-specific docs at distinct levels.

#### Scenario: Root README links to module details
- **WHEN** a workflow needs detailed module-specific parameters, caveats, or examples
- **THEN** the root README SHALL link to the relevant module README or docs file
- **AND** it SHALL avoid duplicating long implementation details that belong in those files

#### Scenario: Change is implemented
- **WHEN** this documentation reorganization is implemented
- **THEN** it SHALL NOT change application code, scripts, Make targets, Ansible playbooks, OpenTofu configuration, inventory, generated outputs, or live infrastructure behavior
- **AND** it SHALL NOT implement roadmap items or archive OpenSpec changes
